/***********************************************************************
 * Source: SAS-master (GitHub)
 *
 * Included as test fixture for sas2ast parser project.
 ***********************************************************************/

/*Basic Statistical Procedures*/

* proc univariate:
creates statistics like mean median, std, skewness, kurtosis
generates
;
data class;
input score @@;
x = _n_-1;
cards;
56 78 84 73 90 44 76 87 92 75
85 67 90 84 74 64 73 78 69 56
87 73 100 54 81 78 69 64 73 65
;
run;

proc univariate data = class;
var score;
run;

proc univariate normal data = class;
var score;
run;

proc sgplot data = class;
scatter x = x y = score;
run;

* create statistical graphics with PROC UNIVARIATE;
* it can create many graphics: (1). cdfplot (2). histogram (3). ppplot (4). probplot (5). qqplot;

proc univariate data = class;
var score;
histogram score / normal;
cdfplot score;
probplot score;
run;

* confidence intervals with PROC MEANS  CLM: confidence limit, alpha = 0.05 or 0.1;
proc means data = class n mean alpha = 0.05 clm;
var score;
run;


* Testing ;

* 1. Testing for continuous data;

* T-Test
* one-sample T-Test: SAS will test whether the mean is significantly differnet from H0 (the default value in H0 is 0);
proc ttest data = class H0=64 alpha=0.05 nobyvar;
var score;
run;

* paired t-test;
data swim;
input semi final @@;
cards;
56 78 84 73 90 44 76 87 92 75
85 67 90 84 74 64 73 78 69 56
87 73 100 54 81 78 69 64 73 65
;
run;

proc ttest data = swim;
paired semi * final;
run;


* 2. Testing for categorical data (PROC FREQ);

data bus;
input bustype $ time $ @@;
cards;
E O E L E L R O E O
E O E O R L R O R L
R O E O R L E O R L
R O E O E O R L E L
E O R L E O R L E O
;
run;

proc format;
value $type 'E' = 'express' 'R' = 'regular';
value $OntimeOrDelay 'L' = 'late' 'O' = 'on time';
run;

proc freq data = bus;
tables bustype * time / chisq;
format bustype $type. time $OntimeOrDelay.;
run;


* correlation;
proc corr data = swim;
var final semi;
*with semi;
run;


* one-way anova;
data heights;
input region $ height @@;
cards;
W 65 W 63 W 58 W 57 W 53 W 56 W 66 W 55
W 55 W 48 W 76 W 71 W 63 W 61 W 58 W 57
E 65 E 57 E 71 E 64 E 66 E 77 E 78 E 61
E 62 E 66 E 76 E 56 E 66 E 55 E 62 E 63
S 41 S 61 S 40 S 45 S 43 S 45 S 65 S 45
S 45 S 56 S 34 S 65 S 39 S 45 S 65 S 67
N 63 N 54 N 67 N 43 N 76 N 78 N 45 N 56
N 65 N 45 N 65 N 57 N 67 N 64 N 65 N 55
;
run;

proc format;
value $direct 'W' = 'West' 'E' = 'East' 'S' = 'South' 'N' = 'North';
run;

proc anova data = heights;
class region;
model height = region;
means region / scheffe;
format region $direct.;
run;
