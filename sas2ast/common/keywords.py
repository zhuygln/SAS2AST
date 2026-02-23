"""SAS keyword sets and operator mappings."""

from __future__ import annotations

# Mnemonic operators → symbolic equivalents
MNEMONIC_OPS = {
    "EQ": "=",
    "NE": "^=",
    "LT": "<",
    "LE": "<=",
    "GT": ">",
    "GE": ">=",
    "AND": "&",
    "OR": "|",
    "NOT": "^",
    "IN": "IN",
}

# SAS statement keywords that start DATA step statements
DATA_STEP_STATEMENTS = frozenset({
    "SET", "MERGE", "UPDATE", "MODIFY",
    "IF", "ELSE", "DO", "END", "SELECT", "WHEN", "OTHERWISE",
    "OUTPUT", "DELETE", "RETURN", "STOP", "ABORT", "LEAVE", "CONTINUE",
    "DROP", "KEEP", "RETAIN", "LENGTH", "FORMAT", "INFORMAT", "LABEL",
    "ARRAY", "BY", "WHERE",
    "INFILE", "INPUT", "FILE", "PUT",
    "CARDS", "DATALINES", "CARDS4", "DATALINES4",
    "CALL",
    "ATTRIB", "RENAME",
})

# Global statements (outside DATA/PROC)
GLOBAL_STATEMENTS = frozenset({
    "LIBNAME", "FILENAME", "OPTIONS", "TITLE", "TITLE1", "TITLE2", "TITLE3",
    "TITLE4", "TITLE5", "TITLE6", "TITLE7", "TITLE8", "TITLE9", "TITLE10",
    "FOOTNOTE", "FOOTNOTE1", "FOOTNOTE2", "FOOTNOTE3", "FOOTNOTE4",
    "FOOTNOTE5", "FOOTNOTE6", "FOOTNOTE7", "FOOTNOTE8", "FOOTNOTE9",
    "FOOTNOTE10", "ODS", "DM", "X", "ENDSAS",
})

# Macro keywords
MACRO_KEYWORDS = frozenset({
    "%MACRO", "%MEND", "%LET", "%PUT", "%IF", "%THEN", "%ELSE",
    "%DO", "%END", "%TO", "%BY", "%WHILE", "%UNTIL",
    "%GLOBAL", "%LOCAL", "%INCLUDE", "%SYSFUNC", "%EVAL",
    "%SYSEVALF", "%STR", "%NRSTR", "%NRBQUOTE", "%BQUOTE",
    "%SUPERQ", "%UNQUOTE", "%QSYSFUNC", "%SCAN", "%SUBSTR",
    "%UPCASE", "%LOWCASE", "%LENGTH", "%INDEX", "%SYMEXIST",
    "%QUPCASE",
})

# Known PROC names for step detection
KNOWN_PROCS = frozenset({
    "SQL", "SORT", "PRINT", "MEANS", "SUMMARY", "FREQ", "TRANSPOSE",
    "IMPORT", "EXPORT", "DATASETS", "CONTENTS", "FORMAT",
    "SGPLOT", "SGPANEL", "GPLOT", "GCHART",
    "REG", "LOGISTIC", "GLM", "MIXED", "GENMOD", "PHREG",
    "LIFETEST", "UNIVARIATE", "CORR", "TTEST", "ANOVA",
    "TABULATE", "REPORT", "COMPARE",
    "APPEND", "COPY", "DELETE",
    "ARIMA", "ESM", "EXPAND", "TIMESERIES",
    "ROBUSTREG", "STDIZE", "GINSIDE", "KCLUS",
    "HPDS2", "FEDSQL",
})

# Procs terminated by QUIT instead of RUN
QUIT_PROCS = frozenset({"SQL", "DATASETS"})

# Step boundary keywords
STEP_TERMINATORS = frozenset({"RUN", "QUIT"})

# CARDS/DATALINES keywords (followed by raw data until lone ; or ;;;;)
CARDS_KEYWORDS = frozenset({"CARDS", "DATALINES", "CARDS4", "DATALINES4"})
