#!/bin/bash
# The interpreter used to execute the script

#“#SBATCH” directives that convey submission options:

#SBATCH --job-name=preprocess_yahoo_data
#SBATCH --mail-user=leeyongs@umich.edu
#SBATCH --mail-type=BEGIN,END
#SBATCH --nodes=1
#SBATCH --gpus-per-node=v100:1
#SBATCH --partition=gpu
#SBATCH --output=/home/%u/%x-%j.log
#SBATCH --mem-per-cpu=5GB
#SBATCH --time=00-08:00:00

BASE_PATH=/home/leeyongs/proj/592-Project

eval "$(conda shell.bash hook)"
conda activate $BASE_PATH/envs


bash $BASE_PATH/scripts/gpt2/tools/process_data_yahoo.sh $BASE_PATH 0
