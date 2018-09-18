import os
import re
import gzip
import random
import datetime
import time
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.switch_backend('agg')
from contextlib import redirect_stdout
import argparse

import keras
from keras import callbacks
from keras import optimizers
from keras.models import Sequential,load_model
from keras.layers import Dense,LSTM,Dropout,GRU,RNN
from keras.layers.embeddings import Embedding
from sklearn.metrics import classification_report,roc_auc_score,accuracy_score
from sklearn.metrics import roc_curve, auc
from sklearn.utils import shuffle
from imblearn.under_sampling import RandomUnderSampler


parser = argparse.ArgumentParser(description='VirNet a deep neural network model for virus identification')
parser.add_argument('--mode', dest='mode',type=bool, default=False, help='if you want train mode (0) or eval mode (1) (default: 0)')
parser.add_argument('--input_dim', dest='input_dim', type=int, default=100, help='input dim (default: 100)')
parser.add_argument('--batch_size', dest='batch_size', type=int, default=512, help='Batch size (default: 512)')
parser.add_argument('--cell_type', dest='model_name', default='lstm', help='model type which is lstm,gru,rnn (default: lstm)')
parser.add_argument('--n_layers', dest='n_layers', type=int, default=1, help='number of layers(default: 1)')
parser.add_argument('--n_neurons', dest='nn', type=int, default=128, help='number of neurons(default: 128)')
parser.add_argument('--lr', dest='lr', type=float, default=0.01, help='learning rate(default: 0.01)')
parser.add_argument('--epoch', dest='ep', type=int, default=30, help='number of epochs(default: 30)')
parser.add_argument('--data', dest='data', default='../../data/3-fragments/fna', help='train mode (mode =0) Training and Testing data dir, eval mode (mode =1) path of test file')
parser.add_argument('--sample', dest='is_sample', type=bool, default=False, help='Training and Testing data dir')
parser.add_argument('--model_path', dest='model_path', default='model.h5', help='in case you are in in eval model ')


args = parser.parse_args()
model_name=args.model_name
input_dim=args.input_dim
output_dim=1
nn=args.nn
n_layers=args.n_layers
ep=args.ep
batch_size=args.batch_size
data_dir=args.data
lr=args.lr

experiment_name='{0}_I{1}_L{2}_N{3}_ep{4}_lr{5}'.format(model_name,input_dim,n_layers,nn,ep,lr)
data_file='{0}_{1}.fna_{2}.csv'
if(args.mode):
    model_path=args.model_path
else:
    model_path='models/model_'+experiment_name+'{epoch:02d}-{val_acc:.2f}.h5'
genomes=['non-viral','viral']
logs=[]



def load_data():
    def load_fasta(file_path):
        data_list=[]
        for record in SeqIO.parse(file_path, "fasta"):
            data_list.append([record.id,str(record.seq)])
        print('Loaded {0} fragments'.format(len(data_list)))

        df=pd.DataFrame(data_list,columns=['ID','SEQ'])
        return df

    def load_csv_fragments(genome,ty,input_dim):
        data_path=os.path.join(data_dir,data_file.format(genome,ty,input_dim))
        #df=pd.read_csv(data_path)
        df=load_fasta(data_path)
        if genome is 'viral':
            df['LABEL']=1
        else:
            df['LABEL']=0
        return df
        
    print('Loading training and testing data')
    df_train=pd.DataFrame()
    df_test=pd.DataFrame()
    for genome in genomes:
        df_train=df_test.append(load_csv_fragments(genome,'train',input_dim))
        df_test=df_test.append(load_csv_fragments(genome,'test',input_dim))

    print('Training len {0}'.format(len(df_train)))
    print('Testing len {0}'.format(len(df_test)))

    if(args.is_sample):
        n_sample=500
        print('Sample first {0} of data'.format(n_sample))
        df_train=df_train.sample(n_sample)
        df_test=df_test.sample(n_sample)
    return df_train,df_test


def process_data(df_train,is_sample=False):
    print('Preporcessing and Decoding SEQ chars')
    dna_dict={'A':1,'C':2,'G':3,'T':4,'N':5,' ':0}
    def decode(seq):
        new_seq=np.zeros(input_dim)

        ## TODO Replace ambiguous char
        seq=re.sub(r'[^ATGCN]','N',seq.upper())
        for i in range(len(seq[:input_dim])):
            new_seq[i]=dna_dict[seq[i]]
        return new_seq.astype(np.int)
    """    
    dna_list=[' ','A','C','G','T','N']
    def encode(seq):
        new_seq=[]
        for i in seq:
            new_seq.append(dna_list[i])
        return ''.join(new_seq) 
    """
    df_train['SEQ']=df_train['SEQ'].apply(decode)
    X_train=df_train['SEQ'].values.tolist()
    y_train=df_train['LABEL'].values

    if(is_sample):
        print('UnderSample Data')
        rus = RandomUnderSampler(random_state=42)
        rus.fit(X_train, y_train)
        X_train, y_train = rus.sample(X_train, y_train)


    print('Suffle Data')
    X_train , y_train = shuffle(X_train, y_train, random_state=42)
    print('Shape of Data {0}'.format(len(X_train)))

    X_train=np.array(X_train).reshape(len(X_train),input_dim,1)
    #y_train=one_hot_encode(y_train,output_dim)

    return X_train,y_train


# ## Training model
def create_model(model_name,input_dim,output_dim,nn,n_layers):
    print('Creating {0} Model'.format(model_name))
    model = Sequential()
    if model_name == 'lstm':
        rnn_cell=LSTM
    elif model_name == 'gru':
        rnn_cell=GRU
    elif model_name == 'rnn':
        rnn_cell=RNN
    else:
        rnn_cell=LSTM

    if(n_layers>1):
        model.add(rnn_cell(nn,kernel_initializer='normal',input_shape=(input_dim,1),return_sequences=True,recurrent_dropout=0.1))
        for _ in range(n_layers-2):
                model.add(rnn_cell(nn,kernel_initializer='normal',return_sequences=True,recurrent_dropout=0.1))
        model.add(rnn_cell(nn,kernel_initializer='normal',recurrent_dropout=0.1))
    else:
        model.add(rnn_cell(nn,kernel_initializer='normal',input_shape=(input_dim,1),recurrent_dropout=0.1))

    model.add(Dropout(0.2))
    model.add(Dense(nn//2,kernel_initializer='normal', activation='relu'))
    model.add(Dropout(0.2))
    model.add(Dense(output_dim,kernel_initializer='normal', activation='sigmoid'))
    print(model.summary())
    with open('experiments/{0}_model_arc.txt'.format(experiment_name), 'w') as f:
        with redirect_stdout(f):
            model.summary()
    return model

def train_model(model,X_train,y_train):
    print('Training starting ... ')
    start_t=time.time()
    adam=optimizers.Adam(lr=args.lr)
    model.compile(loss='binary_crossentropy', optimizer=adam, metrics=['accuracy'])
    checkpoint = keras.callbacks.ModelCheckpoint(filepath=model_path, monitor='val_acc', verbose=1)
    earlystop = keras.callbacks.EarlyStopping(monitor='val_acc', min_delta=0.0001, patience=5, verbose=1)
    history=model.fit(np.array(X_train),y_train,batch_size=batch_size, shuffle=True, epochs=ep,validation_split=0.1,verbose=2,callbacks=[checkpoint,earlystop])
    end_t=time.time()
    logs.append('Training time\t{0:.2f} sec\n'.format(end_t-start_t))
    return history

def load_nn_model(model,model_path):
    model.load_weights(model_path)
    return model

def plot_train(history):
    plt.subplot(2, 1, 1)
    plt.plot(history.history['acc'])
    plt.plot(history.history['val_acc'])
    plt.title('model accuracy')
    plt.ylabel('accuracy')
    plt.legend(['train', 'test'], loc='upper left')

    # summarize history for loss
    plt.subplot(2, 1, 2)
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title('model loss')
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.legend(['train', 'test'], loc='upper left')
    #plt.show()
    plt.savefig('experiments/{0}_train_curve.png'.format(experiment_name))
    

def plot_roc_curve(y_test,y_prop):
    # Compute ROC curve and ROC area for each class
    fpr = dict()
    tpr = dict()
    roc_auc = dict()
    fpr[0], tpr[0], _ = roc_curve(y_test, y_prop)
    roc_auc[0] = auc(fpr[0], tpr[0])

    # Compute micro-average ROC curve and ROC area
    fpr["micro"], tpr["micro"], _ = roc_curve(y_test.ravel(), y_prop.ravel())
    roc_auc["micro"] = auc(fpr["micro"], tpr["micro"])
    plt.figure()
    lw = 2
    plt.plot(fpr[0], tpr[0], color='darkorange',
            lw=lw, label='ROC-AUC curve (area = %0.2f)' % roc_auc[0])
    plt.plot([0, 1], [0, 1], color='navy', lw=lw, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC-AUC Curve')
    plt.legend(loc="lower right")
    plt.savefig('experiments/{0}_roc_curve.png'.format(experiment_name))

def predict_classes(proba):
    thresh=0.5
    if proba.shape[-1] > 1:
        return proba.argmax(axis=-1)
    else:
        return (proba > thresh).astype('int32')

def evaluate_model(model,X_test,y_test):
    print('Evaluate model ... ')
    start=time.time()
    target_names = ['Not Virus', 'Virus']
    y_prop=model.predict(X_test,batch_size=1024)
    end=time.time()
    y_pred=predict_classes(y_prop)
    logs.append(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))+'\n')
    logs.append('ROC-AUC:\t{0:.2f}\n'.format(roc_auc_score(y_test, y_prop)))
    logs.append('Accuracy:\t{0:.2f}%\n'.format(accuracy_score(y_test, y_pred)*100))
    logs.append('Classification Report:\n{0}\n'.format(classification_report(y_test, y_pred, target_names=target_names)))
    logs.append('Predicting time\t{0:.2f} sec\n'.format(end-start))
    plot_roc_curve(y_test,y_pred)
    print(''.join(logs))
    with open('experiments/{0}_logs.txt'.format(experiment_name),'w') as f:
        f.write(''.join(logs))
    np.save('experiments/{0}_test_logits.txt'.format(experiment_name), y_prop)

def main():
    print('Starting Experiment {0}'.format(experiment_name))
    df_train,df_test=load_data()
    X_train,y_train=process_data(df_train,is_sample=True)
    X_test,y_test=process_data(df_test,is_sample=False)
    model=create_model(model_name,input_dim,output_dim,nn,n_layers)
    history=train_model(model,X_train,y_train)
    plot_train(history)
    evaluate_model(model,X_test,y_test)

if __name__ == "__main__":
    main()
