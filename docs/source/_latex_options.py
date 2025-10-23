# sudo apt install fonts-lmodern fonts-cmu fonts-lato
latex_engine = "xelatex"
latex_elements = {
    # Additional stuff for the LaTeX preamble.
    # The paper size ('letterpaper' or 'a4paper').
    "papersize": "a4paper",
    # The font size ('10pt', '11pt' or '12pt').
    "pointsize": "11pt",
    # Additional stuff for the LaTeX preamble.
    "preamble": r"""
            \usepackage{fontspec}
            \usepackage[EU1]{fontenc}
            % \renewcommand\rmdefault{cmr}
            % \renewcommand\sfdefault{cmss}
            % \renewcommand\ttdefault{cmtt}
            \setmainfont{Lato}
            \setsansfont{Lato}
            \setmonofont{DejaVu Sans Mono}
            \usepackage{enumitem}
            \setlistdepth{99}
        """,
}
