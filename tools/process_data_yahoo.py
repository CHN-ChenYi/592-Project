import multiprocessing
import os
import time
import torch
import json
import sys
import csv
from numerize.numerize import numerize
import numpy as np
from data_utils.indexed_dataset import make_builder
from transformers import AutoTokenizer
from arguments import get_args


# 1. Implement an Encoder, which gives it a line of input data and it returns you the tokenized result.
class Encoder(object): 
    def __init__(self, args):
        self.args = args

    def initializer(self):
        Encoder.tokenizer = AutoTokenizer.from_pretrained(self.args.model_path)

    def encode(self, line):
        if "question_content" not in line or len(line["question_content"]) == 0:
            if self.args.model_type!="qwen":
                template = (
                    "Below is an title that describes a task. "
                    "Write a response that appropriately completes the request.\n\n"
                    "### title:\n{title}\n\n### Response:\n"
                )
            else:
                template = (
                    "<|im_start|>Below is an title that describes a task. "
                    "Write a response that appropriately completes the request.\n\n"
                    "### title:\n{title}\n\n### Response:\n<|im_end|><|im_start|>Assistant:"
                )
            prompt = template.format(title=line["question_title"])
        else:
            if self.args.model_type!="qwen":
                template = (
                    "Below is an title that describes a task, paired with an input that provides further context. "
                    "Write a response that appropriately completes the request.\n\n"
                    "### title:\n{title}\n\n### Input:\n{content}\n\n### Response:\n"
                )
            else:
                template = (
                    "<|im_start|>Below is an title that describes a task, paired with an input that provides further context. "
                    "Write a response that appropriately completes the request.\n\n"
                    "### title:\n{title}\n\n### Input:\n{content}\n\n### Response:\n<|im_end|><|im_start|>Assistant:"
                )
            prompt = template.format(title=line["question_title"], content=line["question_content"])
            
        response = line["best_answer"]

        prompt_tokens = Encoder.tokenizer.encode(prompt, add_special_tokens=False)
        full_tokens = Encoder.tokenizer.encode(prompt + response, add_special_tokens=False) + [Encoder.tokenizer.eos_token_id]
        response_tokens = full_tokens[len(prompt_tokens):]
        
        if len(prompt_tokens) > self.args.max_prompt_length or len(response) == 0:
            return None, None, None, None, len(line)
        
        return line, prompt, prompt_tokens, response_tokens, len(line)


def main():
    print("OK")
    args = get_args()
        
    args.processed_data_dir = os.path.join(args.processed_data_dir, args.model_type)

    os.makedirs(args.processed_data_dir, exist_ok=True)

    with open(os.path.join(args.data_dir, 'train.csv'), 'r') as f:
        reader = csv.DictReader(f, fieldnames=["topic","question_title","question_content","best_answer"])
        train_data = list(reader)
    with open(os.path.join(args.data_dir, 'test.csv'), 'r') as f:
        reader = csv.DictReader(f, fieldnames=["topic","question_title","question_content","best_answer"])
        test_data = list(reader)
    raw_data = test_data + train_data

    with open(os.path.join(args.data_dir, "classes.txt")) as f:
        classes = f.readlines()
    classes.insert(0, "None")

    if (args.class_index != 0):
        raw_data = [row for row in raw_data if row['topic'] == str(args.class_index)]
    for i in range(len(raw_data)):
        for key in raw_data[i]:
            if isinstance(raw_data[i][key], str):
                raw_data[i][key] = raw_data[i][key].replace('\\n', '\n')

    if args.dev_num > 0:
        all_data = {
            "valid": raw_data[:int(args.dev_num * 1.1)],
            "train": raw_data[int(args.dev_num * 1.1):]
        }
        data_len = {
            "valid": args.dev_num,
            "train": args.train_set_size if args.train_set_size > 0 else len(all_data["train"])
        }
    else:
        all_data = {
            "train": raw_data
        }
        data_len = {
            "train": args.train_set_size if args.train_set_size > 0 else len(all_data["train"])
        }
    if data_len["train"] * 1.1 < len(all_data["train"]):
        all_data["test"] = all_data["train"][int(data_len["train"] * 1.1):]
        all_data["train"] = all_data["train"][:int(data_len["train"] * 1.1)]
        data_len["test"] = min(args.test_set_size, len(all_data["test"])) if args.test_set_size > 0 else len(all_data["test"])
    else:
        data_len["train"] = min(data_len["train"], len(all_data["train"]))

    print(f"expected_data_len: {data_len}")
    print(f"actual_data_len: { {key: len(value) for key, value in all_data.items()} }")

    for split in all_data:
        # encoder use the tokenizer to encode data
        encoder = Encoder(args)

        # 2. Mapping all datas with Encoder, with the help of multiprocessing
        pool = multiprocessing.Pool(processes=args.data_process_workers, initializer=encoder.initializer)
        encoded_docs = pool.imap_unordered(encoder.encode, all_data[split], chunksize=50)
        proc_start = time.time()
        total_bytes_processed = 0
        
        bin_file = os.path.join(args.processed_data_dir, f"{split}_{0}.bin")
        idx_file = os.path.join(args.processed_data_dir, f"{split}_{0}.idx")

        if args.model_type!="qwen":
            binary_builder = make_builder(bin_file, impl="mmap", dtype=np.uint16)
        else:
            binary_builder = make_builder(bin_file, impl="mmap", dtype=np.uint32)

        # put tokenized data into binary_builder
        inst_num = 0
        print("#"*10, split, "#"*10)
        
        prompt_lens = []
        response_lens = []
        
        json_file = open(os.path.join(args.processed_data_dir, f"{split}.jsonl"), "w")
        
        item_processed = 0

        for lid, (line, prompt_str, prompt, response, bytes_processed) in enumerate(encoded_docs):
            total_bytes_processed += bytes_processed
            if prompt is None:
                continue

            if item_processed == data_len[split]:
                if lid % 1000 == 0:
                    current = time.time()
                    elapsed = current - proc_start
                    mbs = total_bytes_processed / elapsed / 1024 / 1024
                    print(f"Processed {lid} documents. {inst_num} instances.",
                        f"({lid/elapsed} docs/s, {mbs} MB/s).",
                        file=sys.stderr)
                continue

            if args.only_prompt:
                if len(prompt) < args.max_length:
                    binary_builder.add_item(torch.IntTensor(prompt))
                else:
                    continue
            else:
                binary_builder.add_item(torch.IntTensor(prompt + [-1] + response))

            item_processed += 1

            json_file.write(json.dumps({
                "instruction": line["question_title"],
                "prompt": prompt_str,
                "input": line["question_content"],
                "output": line["best_answer"],
            }) + "\n")

            prompt_lens.append(len(prompt))
            response_lens.append(len(response))

            inst_num += 1
            if lid % 1000 == 0:
                current = time.time()
                elapsed = current - proc_start
                mbs = total_bytes_processed / elapsed / 1024 / 1024
                print(f"Processed {lid} documents. {inst_num} instances.",
                    f"({lid/elapsed} docs/s, {mbs} MB/s).",
                    file=sys.stderr)

        # finish compressing tokenized data into `bin_file`, and generate meta information into `idx_file`
        binary_builder.finalize(idx_file)

        # close multiproceessing mapping
        pool.close()
        json_file.close()
                
        print("Data num", len(prompt_lens))
        print("Prompt lengths.", "Mean:", np.mean(prompt_lens), "Max:", np.max(prompt_lens), "Min:", np.min(prompt_lens))
        print("Response", "Mean:", np.mean(response_lens), "Max:", np.max(response_lens), "Min:", np.min(response_lens))


if __name__ == '__main__':
    main()
