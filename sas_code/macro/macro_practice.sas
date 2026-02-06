/***********************************************************************
 * Source: SAS-master (GitHub)
 *
 * Included as test fixture for sas2ast parser project.
 ***********************************************************************/

/* macro */

* define macro variable and invoke macro variable;
* e.g.1;
%let country = 'USA';
proc print data = sashelp.cars;
where origin = &country;
run;

* e.g.2;
%let country = USA;
%let number = 6;
proc print data = sashelp.cars;
* referencing a macro variable by using double quotes;
where origin = "&country" and cylinders = &number;
run;

* e.g.3;
data example3;
input a b;
cards;
31 76
76 92
62 37
;
run;
%macro printData(data);
proc print data = &data;
run;
%mend printData;

%printData(example3);


* Conditional and Iterative Statement;
* iterative statement;
* calculate the average weight for different cylinders = 4,6,8,10.;
proc freq data = sashelp.cars;
tables cylinders;
run;

* method 1: PROC SORT + PROC MEANS;
proc sort data = sashelp.cars out = sorted;
by cylinders;
run;
proc means data = sorted mean;
var weight;
by cylinders;
run;

* method 2: MACRO, does not need to use PROC SORT;
%macro CalAvg;
%do i = 4 %to 10 %by 2;
proc means data = sashelp.cars(where = (cylinders = &i)) mean;
var weight;
title "Average weight of cars with cylinders = &i";
run;
%end;
%mend CalAvg;

%CalAvg;
title;


/*self-invode*/
%macro mysum(n);
%if &n > 1 %then %eval(&n + %mysum(%eval(&n - 1)));
%else &n;
%mend mysum;

%put %mysum(4);
