# VirNet
VirNet: A deep attention model for viral reads identification

This tool is able to identifiy viral sequences from a mixture of viral and bacterial sequences. Also, it can purify viral metagenomic data from bacterial contamination


## For Use

The first step is to have a fasta file format and specify the input dimention you want to work with. 
We support n=100,500,1000 and 3000 only. 

```
python predict.py --input_dim=500 --input=data/test/data.fna --output=output.csv

```

## For Training

```
python train.py --input_dim=<n> --data=<data_folder> --work_dir=<work_dir>
```

## Conference 
http://www.icces.org.eg