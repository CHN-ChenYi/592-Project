BASE_PATH=${1}
CLASS_INDEX=${2:-1}

export TF_CPP_MIN_LOG_LEVEL=3

# only prompt for MiniLLM train
PYTHONPATH=${BASE_PATH} python3 ${BASE_PATH}/tools/process_data_yahoo.py \
    --data-dir ${BASE_PATH}/data/yahoo/yahoo_answers_csv/ \
    --processed-data-dir ${BASE_PATH}/processed_data/yahoo/prompt \
    --model-path ${BASE_PATH}/checkpoints/gpt2-large \
    --data-process-workers 32 \
    --max-prompt-length 256 \
    --dev-num 1000 \
    --class-index ${CLASS_INDEX} \
    --only-prompt \
    --model-type gpt2

# prompt and response for baselines
PYTHONPATH=${BASE_PATH} python3 ${BASE_PATH}/tools/process_data_yahoo.py \
    --data-dir ${BASE_PATH}/data/yahoo/yahoo_answers_csv/ \
    --processed-data-dir ${BASE_PATH}/processed_data/yahoo/full \
    --model-path ${BASE_PATH}/checkpoints/gpt2-large \
    --data-process-workers 32 \
    --max-prompt-length 256 \
    --dev-num 1000 \
    --class-index ${CLASS_INDEX} \
    --model-type gpt2
