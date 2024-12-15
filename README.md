# LLM Annotator

This is a simple script for developing and applying LLM prompts, both text and text+image, in bulk.

## Setup

To install the necessary dependencies, run something similar to the following:

```
python3 -m venv local
source local/bin/activate
pip install -r requirements.txt
```

By default, the script assumes that the `Llama-3.2-Vision-Instruct` model can be found under your home directory at `~/corpora/models/Llama-3.2-11B-Vision-Instruct`, i.e. files like `config.json` and `model-00001-of-00005.safetensors` are present there.  If it's in another location, or you want to use a different model (not tested), the script can be invoked with the `--model PATH` option.

## Usage

The basic idea is that you have **items** of interest (potentially with associated **images**), and **questions** you want to ask about them.

### Direct questions

A simple way to verify things work, and to quickly try out a new question, is the `--ad_hoc QUESTION IMAGE` option.  For instance, this repository has a file named `text_image.png`, so you could run:

```
python annotate.py --ad_hoc "When was Horace born?" "methodist_newsletter.png"
```

The model should respond with something like:

```
Horace L. Bray was born on March 18, 1831.
```

That's because the image contains a description of this particular individual.  If instead of an image you passed empty double-quotes to the script:

```
python annotate.py --ad_hoc "When was Horace born?" ""
```

The model will use its general context in guessing what you intend:

```
There are several historical figures named Horace, but the most famous one is likely the Roman poet Quintus Horatius Flaccus, commonly known as Horace. He was born on December 8, 65 BCE, in Venusia, Italy.
```

Finally, a slightly more careful question:

```
python annotate.py --ad_hoc "When was Horace born? Answer just with the year." "methodist_newsletter.png"
```

Can get the model to respond in a more focused way:

```
1831
```

Which you can imagine using in further automatic steps:

```
python annotate.py --ad_hoc "What famous authors died in the year 1831?" ""
```

And so forth.

### Flexibly scaling up

As described above, a sequence of dependent questions and associated images could be strung together, and applied to each in a long list of **items**.  This script lets you do this by entering information in a couple simple spreadsheets, or **tab-separated files**.  This is easiest to see by example, so here is how one could generalize the name/birth/death task previously shown using `--ad_hoc`.

When not run in "ad hoc" mode, the script is used in this fashion, and in fact you can run this exact command:

```
python annotate.py --items items.tsv --questions questions.tsv --output answers.tsv
```

As you can see, it requires two tab-separated files, corresponding to the **items** and the **questions**, and produces one tab-separated file (which is just the **items** file again, but with additional columns containing the model's answers).  You can actually run the above command verbatim, because this repository has suitable `items.tsv` and `questions.tsv` files, which we'll look at below.  Note that these tab-separated files start with *header* rows, and the names of the columns are important.

#### The items file

| name   | source                          |
| ------ | ------------------------------- |
| Horace | methodist\_newsletter           |
| Mary   | handwritten\_birth\_certificate |

The **items** file can have as many columns you would like, with any reasonable name that **doesn't start with "ANS_"** (otherwise, if it can be used as a variable name in Python, it should be fine). This is entirely specific to your research: maybe you have **items** that are medieval cities, and columns like "name", "population", "latitude", "longitude", "language", "government\_style"...really, whatever is natural and important.  The model will be asked questions about each **item**, independently of all other **items**.

In this toy example, our **items** are *people*, for whom we have names and some notion of what document describes them.  In reality, because it's a domain you care about and have been investigating for a while, you would presumably have many more columns, and many, many more rows: but remember, the quality and consistency of this data is critical!

#### The questions file

| question\_template                               | image\_file\_template |
| ------------------------------------------------ | --------------------- |
| When was {name} born? Answer just with the year. | {source}.png          |
| What famous authors died in the year {ANS\_0}?   |                       |

The **questions** file is where the real craftsmanship begins.  Unlike the open-ended **items** file, it has exactly two columns, which always have the same names: "question\_template" and "image\_file\_template".  If you look at the first non-header row, it's probably fairly intuitive what happens: the values of a given **item** are substituted in for the field-names in curly braces to get a particular question (e.g. "When was Horace born? Answer just with the year.") and image file path (e.g. "methodist\_newsletter.png"), and those are used the same way as when we used `--ad_hoc`. There always has to be a question\_template, and it can use any of the fields from the **items** file. The image\_file\_template can be blank, in which case no image is given to the model, but if it's not blank, it must expand to a file path that's a valid image where the script is being invoked.

But there are two **questions** in this file (i.e. non-header rows), and the second one has curly-braces containing a field that's not in the **items** file. A field of the form `ANS\_NUMBER` will be substituted with the **answer**, for the current **item**, to the earlier **question** corresponding to the number (starting with 0). Note how the first template is phrased to try and avoid superfluous text in the answer and make it more suitable for use in the following template. Also, bear in mind that while a row can only refer to **answers** generated earlier, all rows can use any fields from the **items** file, the second template in this example just happens not to.

#### The output file

The script's output is simply the original **items** TSV file, with new columns containing **answers**. For our example, this might look like:


| name   | source                          | ANS\_0 | ANS\_1                                          |
| ------ | ------------------------------- | ------ | ----------------------------------------------- |
| Horace | methodist\_newsletter           | 1831   | Some famous authors who died in 1831...         |
| Mary   | handwritten\_birth\_certificate | 1896   | Some notable authors who passed away in 1896... |


If an **output** file isn't specified, the format will be the same but everything will be written to terminal: this can be useful for trying something quickly in `--ad_hoc` mode, but otherwise you most likely want to specify an output file.

## Final thoughts

The second answer column in the example output above is truncated because 1) the answers are quite long and 2) they aren't very accurate, with a tendency to explicitly state "so-and-so didn't die in 1831, but in 1835, which is close" etc. The questions should be improved quite a bit, and that is also a useful way to employ the script: you could put many different formulations into the **questions** file and easily examine their responses side-by-side to find the best performer, only accept answers that multiple formulations agree upon, and so forth.

Moreover, at the time of first commit the `annotate.py` script (which needs to be documented with comments, see below) is less than 130 lines, so it's very easy to glean the basic procedure for generating answers to questions with optional images. Once a researcher has confirmed that a model has useful abilities w.r.t. their domain, it may be best to adapt the script to its specific needs. For instance, custom processing of model answers could extract only numbers that are valid zip-codes, or perform named-entity recognition using [spaCy](https://spacy.io/) to find geographic locations, or make conditional decisions or construct questions on-the-fly, etc. A modest amount of code could be transformative for particular goals.

## To do (the script is usable now, but these are very important to address)

* Make generation as deterministic as possible
* Speed up by batching at the question level
* Document code with in-line comments
