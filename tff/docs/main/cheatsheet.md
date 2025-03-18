## Interchange with external annotation tools

``` python
from tff.convert.addnlp import NLPipeline
```

``` python
NLPipeline()
```
:   generate plain text, feed into NLP, ingest results
:   `tff.convert.addnlp`

---

## XML / TEI import

``` python
from tff.convert.xml import XML
```

``` python
X = XML(...)
```
:   convert XML source to full-fledged TF dataset plus app but no docs;
    put in your own conversion code, if you wish;
    see [Greek New Testament](https://nbviewer.org/github/ETCBC/nestle1904/blob/master/programs/tfFromLowfat.ipynb)
:   `tff.convert.xml`

``` python
from tff.convert.tei import TEI
```

``` python
T = TEI(...)
```
:   convert TEI source to full-fledged TF dataset plus app plus docs
:   `tff.convert.tei`

---

## WATM export

``` python
from tf.app import use
from tff.convert.watm import WATM
```

``` python
A = use(...)
WA = WATM(A, ns, ...)
WA.makeText()
WA.makeAnno()
WA.writeAll()
WA.testAll()
```
:   convert TF dataset to text tokens and annotations in JSON format,
    for consumption by TextRepo/AnnoRepo of
    [KNAW/HuC Digital Infrastructure](https://di.huc.knaw.nl/text-analysis-en.html).
    See
    [Mondriaan Proeftuin](https://github.com/annotation/mondriaan)
    [Suriano Letters](https://gitlab.huc.knaw.nl/suriano/letters)
    [HuygensING/translatin-manif](https://github.com/translatin-manif)
:   `tff.convert.watm`

``` python
from tff.convert.watm import WATMS
```

``` python
W = WATM(org, repo, backend, ns, ...)
W.produce()
```
:   convert series of TF datasets to WATM
:   `tff.convert.watm.WATMS`

---

## NLP import

**in order to use this, install Spacy, see `tff.tools.myspacy`**

``` python

from tff.convert.addnlp import addTokensAndSentences
```

``` python
newVersion = addTokensAndSenteces(A)
```
:   add NLP output from Spacy to an existing
    TF dataset. See the docs how this is broken down in separate
    steps.
:   `tff.convert.addnlp`

---

# Command-line tools

(these work on the command-line if TF is installed)

``` sh
tff-xmlschema analysis {schema}.xsd
```
:   Analyses an XML *schema* file and extracts meaningful information for processing
    the XML that adheres to that schema.
:   `tff.tools.xmlschema`

``` sh
tff-fromxml
```
:   When run in a repo it finds an XML source and converts it to TF. 
    The resulting TF data is delivered in the repo.
    There is a hook to put your own conversion code in.
:   `tff.convert.xml`

``` sh
tff-fromtei
```
:   When run in a repo it finds a TEI source and converts it to TF. 
    The resulting TF data is delivered in the repo.
:   `tff.convert.tei`

``` sh
tff-addnlp
```
:   When run in the repo of a TF dataset, it adds NLP output to it
    after running Spacy to get them.
:   `tff.convert.addnlp`
