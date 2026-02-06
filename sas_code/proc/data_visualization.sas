/***********************************************************************
 * Source: SAS-master (GitHub)
 *
 * Included as test fixture for sas2ast parser project.
 ***********************************************************************/

/*data visualization*/

* figure 1: bar chart with clustered bars ;
data example;
input agegroup $ flavor $ @@;
cards;
A P A C A E C C A G C P
C C C P C P A E A C C C
A G A P C E C C A C A E
A C C P C P A C C P C C
;
run;

proc format;
value $age 'A' = 'Adult' 'C' = 'Child';
value $flav 'P' = 'Pear' 'C' = '80%Cacao' 'G' = 'Ginger' 'E' = 'EarlGrey';
run;

* bar chart shows the number of respondants in each age group who chose each flavor;
proc sgplot data  = example;
vbar flavor / group = agegroup groupdisplay = cluster;
format agegroup $age. flavor $flav.;
label flavor = 'Flavor of Chocolate';
title  'Favoriate Chocolate Flavors by Age';
run;


* figure2: Histograms and Density Curves. Histograms provide us a simple way to
visualize continuous data;
data contest;
input num_books @@;
cards;
4 9 10 6 5 2 7 7 4 5 6 7 8 9 5 4 2
10 4 5 6 8 13 14 16 19 21 3 4 5 6 5
;
run;
proc sgplot data = contest;
histogram num_books / binwidth = 2 showbins scale = count ;
density num_books;
density num_books / type = kernel;
title 'Reading contest';
run;



* figure3: box plots: show the distribution of continuous data, it can exactly
tell us the multiple quantiles of data;
data bike;
input age $ laps @@;
cards;
A 44 A 33 Y 33 M 38 A 40
M 32 Y 32 Y 38 Y 33 A 47
M 37 M 46 Y 34 A 42 Y 24
M 33 A 44 Y 35 A 49 A 38
A 39 A 42 A 32 Y 42 Y 31
M 33 A 33 M 32 Y 37 M 40
;
run;

proc format;
value $agegroup  'A' = 'Adult' 'Y' = 'Youth' 'M' = 'Masters';
run;


proc sgplot data = bike;
vbox laps / category = age;
format age $agegroup.;
title 'Results by Age group';
run;



* figure4: scatter plots an effective way to show the relationship between two continuous variables;
* plot wingspan by length;
data wings;
input type $ length wingspan @@;
cards;
S 28 41 R 102 244 R 50 110
R 66 180 S 23 31 S 11 19
R 100 234 S 53 100 S 60 60
R 15 27 R 140 300
;
run;

proc format;
value $birdtype 'S' = 'songbirds' 'R' = 'raptors';
run;

proc sgplot data = wings;
scatter x = wingspan y = length / group = type;
format type $birdtype.;
title 'Comparsion of Wingspan vs. Length';
run;


* series plots;
data example;
input freq@@;
year = intnx('year', '01jan1970'd, _n_-1);
format year year4.;
cards;
97 154 137.7 149 164 157 188 204 179 210 202 218 209
204 211 206 214 217 210 219 211 233 316 221 239
215 228 219 239 224 234 227 298 332 245 357 301 389
;
run;
title;
proc sgplot data = example;
series x = year y = freq / markers;
run;

proc gplot data = example;
plot freq*year;
run;



* fitted curves;
proc sgplot data = example;
reg x = year y = freq / nomarkers clm nolegclm;
loess x = year y = freq;
pbspline x = year y = freq;
run;


* advanced methods with controlling axes and referene lines;
data example2;
input freq1 freq2@@;
year = intnx('year', '01jan1970'd, _n_-1);
format year year4.;
cards;
97 154 137.7 149 164 157 188 204 179 210 202 218 209
204 211 206 214 217 210 219 211 233 316 221 239
215 228 219 239 224 234 227 298 332 245 357 301 389
;
run;

proc print data = example2;
run;

proc sgplot data = example2;
scatter x = year y = freq1;
series x = year y = freq2;
keylegend / location = inside position = topright;
inset 'This is an example' 'try' / position = topleft;
yaxis  label = 'freq';
xaxis  label = 'year';
run;



* customizing graph attributes
* when creating graphs, we would like to make it attractive and easy to read.
* there might be some times when you want stars instead of circles, or thicker lines, or a different color.
* SGPLOT procedure includes options for controlling graph attributes;
proc sgplot data = example2;
* scatter plots with a filled circle 2mm in size;
scatter x = year y = freq1 / markerattrs = (symbol = circlefilled size = 3MM);
* series plots a line with 2mm thickness and 50% transparency;
series x = year y = freq2 / lineattrs = (thickness = 2MM pattern = dash) transparency = 0.5 ;
* axis lables and titles are b old;
xaxis labelattrs = (weight = bold);
yaxis label = 'freq' labelattrs = (weight = bold);
title bold 'this is title (bold)';
* legend, by default, is outside;
keylegend / location = inside position = topleft;
run;


* panel graphs
* differences between sgplot and sgpanel: (1). SGPLOT creates one-celled graphs (2). SGPANEL can generate multi-celled graphs;
* SGPANEL creates a separate cell for each combination of values of the classification variables that you specify;
* each of those cells uses the same variables on their X and Y axes;
title;
data wings;
input type $ length wingspan @@;
cards;
S 28 41 R 102 244 R 50 110
R 66 180 S 23 31 S 11 19
R 100 234 S 53 100 S 60 60
R 15 27 R 140 300
;
run;

proc format;
value $birdtype 'S' = 'songbirds' 'R' = 'raptors';
run;

proc sgpanel data = wings;
panelby type / novarname spacing = 5;
scatter x = wingspan y = length;
format type $birdtype.;
run;


* saving graphics output
* it is especially important when you want to create a presentation or to write a paper;
ods listing gpath = 'C:\Users\xy\Desktop\time series data' style = journal;
ods graphics / reset
	imagename = 'birdgraph'
	outputfmt = bmp
	height = 2in width = 3in;
proc sgplot data = wings;
scatter x = wingspan y = length;
run;
