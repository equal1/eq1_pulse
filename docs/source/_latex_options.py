# sudo apt install fonts-lmodern fonts-cmu fonts-lato
latex_engine = "xelatex"
latex_elements = {
    # Additional stuff for the LaTeX preamble.
    # The paper size ('letterpaper' or 'a4paper').
    "papersize": "a4paper",
    # The font size ('10pt', '11pt' or '12pt').
    "pointsize": "9pt",
    # Additional stuff for the LaTeX preamble.
    "preamble": r"""
            \usepackage{fontspec}"""
    # + r"\usepackage[EU1]{fontenc}"
    + r"""
            % \renewcommand\rmdefault{cmr}
            % \renewcommand\sfdefault{cmss}
            % \renewcommand\ttdefault{cmtt}
            \setmainfont{Lato}
            \setsansfont{Lato}
            \setmonofont{DejaVu Sans Mono}
            \usepackage{enumitem}
            \setlistdepth{99}

            % Lato (our main/sans font) doesn't cover every glyph we use in the
            % docs (e.g. some Greek letters, arrows, dingbats). newunicodechar
            % lets us route just those specific characters to a fallback font
            % with broader Unicode coverage, instead of switching the whole
            % document's font. DejaVu Sans is bundled with MiKTeX/most TeX
            % distributions, so this doesn't depend on an extra font install.
            \usepackage{newunicodechar}
            \newfontfamily{\unicodefallback}{DejaVu Sans}
            \newunicodechar{μ}{{\unicodefallback μ}}
            \newunicodechar{τ}{{\unicodefallback τ}}
            \newunicodechar{→}{{\unicodefallback →}}
            \newunicodechar{↔}{{\unicodefallback ↔}}
            \newunicodechar{✅}{{\unicodefallback ✅}}
            \newunicodechar{❌}{{\unicodefallback ❌}}
        """,
}
