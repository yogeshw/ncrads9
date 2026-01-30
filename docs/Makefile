# Makefile for NCRADS9 LaTeX Documentation

LATEX = pdflatex
LATEXFLAGS = -interaction=nonstopmode
LATEX_DIR = latex
MAIN = ncrads9_manual

.PHONY: all clean pdf html

all: pdf

pdf: $(LATEX_DIR)/$(MAIN).pdf

$(LATEX_DIR)/$(MAIN).pdf: $(LATEX_DIR)/$(MAIN).tex
	cd $(LATEX_DIR) && $(LATEX) $(LATEXFLAGS) $(MAIN).tex
	cd $(LATEX_DIR) && $(LATEX) $(LATEXFLAGS) $(MAIN).tex
	cd $(LATEX_DIR) && $(LATEX) $(LATEXFLAGS) $(MAIN).tex

clean:
	cd $(LATEX_DIR) && rm -f *.aux *.log *.toc *.out *.lof *.lot *.bbl *.blg *.idx *.ind *.ilg

distclean: clean
	cd $(LATEX_DIR) && rm -f $(MAIN).pdf

help:
	@echo "Available targets:"
	@echo "  all       - Build PDF documentation (default)"
	@echo "  pdf       - Build PDF from LaTeX sources"
	@echo "  clean     - Remove auxiliary files"
	@echo "  distclean - Remove all generated files including PDF"
	@echo "  help      - Show this help message"
