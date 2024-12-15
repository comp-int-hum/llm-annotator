import torch
from transformers import MllamaForConditionalGeneration, AutoProcessor
import accelerate
import re
from PIL import Image
import csv
import os.path
import logging
import sys
import argparse

logger = logging.getLogger("annotate")

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--questions",
        dest="questions",
        help="TSV file with 'question_template' and 'image_file_template' columns (must have header row)."
    )
    parser.add_argument("--items", dest="items", help="TSV file of items to ask questions about (must have header row).")
    parser.add_argument("--output", dest="output", help="TSV output file for the original items plus the answers to the questions.")
    parser.add_argument("--max_tokens", dest="max_tokens", type=int, default=100, help="Maximum tokens to generate in response")
    parser.add_argument(
        "--dry_run",
        dest="dry_run",
        default=False,
        action="store_true",
        help="Don't load or invoke model, just print the prompts/image file names that would be used."
    )
    parser.add_argument(
        "--model",
        dest="model",
        default=os.path.expanduser("~/corpora/models/Llama-3.2-11B-Vision-Instruct"),
        help="Model to use: can be a local path, or Huggingface reference, but should probably resolve to a Llama+vision architecture."
    )
    parser.add_argument(
        "--ad_hoc",
        dest="ad_hoc",
        default=None,
        nargs=2,
        help="If specified, the two values will be used directly as prompt and image file (if the second value is an empty string, no image will be passed)."
    )
    parser.add_argument(
        "--log_level",
        dest="log_level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level: "
    )
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    known_answers = {}

    if not args.dry_run:
        model = MllamaForConditionalGeneration.from_pretrained(args.model, torch_dtype=torch.bfloat16, device_map="auto")
        processor = AutoProcessor.from_pretrained(args.model)

    questions = []
    images = []
    if args.questions:
        with open(args.questions, "rt") as ifd:
            c = csv.DictReader(ifd, delimiter="\t")
            for row in c:
                questions.append(row["question_template"])
                images.append(row["image_file_template"])
    elif args.ad_hoc:
        questions.append(args.ad_hoc[0])
        images.append(args.ad_hoc[1])
    else:
        raise Exception("You must specify either TSV files for the prompts and items, or use `--ad_hoc` with two arguments.")

    fieldnames = []
    items = []
    if args.items:
        with open(args.items, "rt") as ifd:
            c = csv.DictReader(ifd, delimiter="\t")
            fieldnames = c.fieldnames
            for row in c:
                items.append(row)
    else:
        items.append({})
    with (open(args.output, "wt") if args.output else sys.stdout) as ofd:
        if not args.dry_run:
            cfd = csv.DictWriter(ofd, fieldnames=fieldnames + ["ANS_{}".format(i) for i in range(len(questions))], delimiter="\t")
            cfd.writeheader()
        for item_num, item in enumerate(items):
            logger.warning("Processed item #%d", item_num + 1)
            for i, (question_t, image_t) in enumerate(zip(questions, images)):
                question = question_t.format(**item)            
                image = None
                image_file = None
                if image_t:
                    image_file = image_t.format(**item)
                    image = Image.open(image_file)
                if args.dry_run:
                    logger.warning("I would have asked the model%s: %s", " (with image '{}' in context)".format(image_file) if image_file else "", question)
                    ans = str(i)
                elif (question, image_file) not in known_answers:
                    prepped = [
                        {
                            "role" : "user",
                            "content" : ([{"type" : "image"}] if image_t else []) + [
                                {
                                    "type" : "text",
                                    "text" : question
                                }
                            ]
                        }
                    ]
                    inp = processor.apply_chat_template(prepped, add_generation_prompt=False)
                    inpp = processor(image, inp, add_special_tokens=False, return_tensors="pt").to(model.device)
                    output = model.generate(**inpp, max_new_tokens=args.max_tokens)
                    ans = re.sub(
                        r"^.*\<\|end_header_id\|\>(.*?)(\<\|eot_id\|\>)?$",
                        r"\1",
                        processor.decode(output[0]).strip(),
                        flags=re.S
                    ).strip()
                    known_answers[(question, image_file)] = ans
                else:
                    ans = known_answers[(question, image_file)]
                item["ANS_{}".format(i)] = ans
            if not args.dry_run:
                cfd.writerow(item)
