# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile diagrams clean_diagrams

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

distclean:
	@rm -rvf source/_autosummary
	-@find  ./build -mindepth 1 -maxdepth 1 -not -name html -exec rm -rvf \{\} \;
	-@find  ./build/html -mindepth 1 -maxdepth 1 -not -name \\.git* -exec rm -rvf \{\} \;

deploy:
	rsync  -av --delete --no-p --no-g --chmod=ugo=rwX build/html/ engweb:/projects/engweb/eq1lab/

PORT ?= 18182

serve:
	(cd build/html && python -m http.server ${PORT})
