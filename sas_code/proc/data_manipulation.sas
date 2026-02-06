/***********************************************************************
 * Source: SAS-master (GitHub)
 *
 * Included as test fixture for sas2ast parser project.
 ***********************************************************************/

/*Data Manipulation*/

/*1. Data step*/
*--------------------------------------------------------------------------------------------------------------;
* set two data sets
*-----------------------------------------;
* case 1: Stacking data bu Using SET statement;
data example;
set sashelp.cars;
keep make model type origin MSRP weight length;
run;

data data1;
set example;
where type = 'SUV';
run;

data data2;
set example;
where type = 'Truck';
run;

data stacked_data;
set data1 data2;
run;
proc print data = stacked_data;
run;

* case 2: Interleaving data sets Using SET statement;
proc sort data = data1 out = sorted1;
by weight;
proc sort data = data2 out = sorted2;
by weight;
run;

data interleaving;
set sorted1 sorted2;
by weight;
run;
proc print data = interleaving;
run;

* by sorting we can get the same results from UNION;
proc sort data = data1 out = sorted1;
by make;
proc sort data = data2 out = sorted2;
by make;
run;

data interleaving2;
set sorted1 sorted2;
by make;
run;
proc print data = interleaving2;
run;


* merge two data sets;
*-----------------------------------------;
* case 1: Combining data sets Using one-to-one merge;
proc sql;
create table data1 as
select
	distinct make,
	avg(weight) as avg_weight
from example
where weight between 2500 and 3500
group by make
order by make;
quit;

proc sql;
create table data2 as
select
	distinct make,
	origin,
	avg(length) as avg_length
from example
where weight between 2000 and 3200
group by make
order by make;
quit;

proc print data = data1;
run;
proc print data = data2;
run;

data one_to_one_merge;
merge data1 data2;
by make;
run;
proc print data = one_to_one_merge;
run;

* now there are some missing values in data set one_to_one_merge, so we will deal with the missing values;
* summarize the frequency and percentage of missing values within the data;
* count the missing values for numeric and character variables;
data info;
set one_to_one_merge;
num_miss = nmiss(avg_weight, avg_length);
char_miss = cmiss(origin);
run;
proc print data = info;
run;

* Methods for summarizing and reporting missing values:PROC FORMAT + PROC FREQ;
proc format;
value $missing_char '' = 'missing' other = 'not missing';
value missing_numeric . = 'missing' other  = 'not missing';
run;

proc freq data = one_to_one_merge;
tables _all_ / missing nocum nopercent;
format _char_ $missing_char. _numeric_ missing_numeric.;
run;

* Using MISSING function to  remove / maintain missing values;
* maintain missing values;
data missing;
set one_to_one_merge;
where missing(avg_length);
run;
proc print data = missing;
run;

* delete missing values;
data without_missing;
set one_to_one_merge;
where not missing(avg_length) and not missing(avg_weight) and not missing(origin);
run;
proc print data = without_missing;
run;


* case 2: Combining data sets Using one-to-many match merge;
* e.g. suppose ypou have data for every state in the U.S. and want to combine it with data for every county!!;
proc sql;
create table large as
select
	*
from example
where weight > 3000
order by origin;
quit;

proc sql;
create table origins as
select
	origin,
	avg(weight) as avg_weight
from example
group by origin
order by origin;
quit;

data one_to_many_merge;
merge large origins;
by origin;
if weight < avg_weight then flag = 'small';
else flag = 'big';
run;
proc print data = one_to_many_merge;
run;


* case 3: Merging Summary Statistics with the original data;
* first summarize the avg weight for each origin (PROC MEANS + BY) remember doing the sort before PROC MEANS;
proc sort data = example;
by origin;

proc means data = example;
var weight;
by origin;
output out = out mean(weight) = avg;
run;
* then merge;
data merge_avg;
merge example out;
by origin;
run;
proc print data = merge_avg;
by origin;
id origin;
run;

* case 4: Combining a Grand total with the original data;
* SAS reads summary data set with a SET statement but only in the first iteration of the DATA step (if _N_ = 1 then set summary_data);
proc means data = example;
var weight;
output out = out mean(weight) = avg_weight;
run;

data summary_merge;
if _N_ = 1 then set out;
set example;
if weight < avg_weight then flag = 'less';
else flag = 'more';
run;
proc print data = summary_merge;
run;

* Project: Suppose one origin has multiple recoreds;
data subset;
set example;
keep origin weight length;
run;
proc print data = subset;
run;

* task 1: find the first obs for each origin;
proc sort data = subset out = sorted;
by origin;
run;
data first;
set sorted;
by origin;
if first.origin;
run;
proc print data = first;
run;


* task 2: find the last obs for each origin;
proc sort data = subset out = sorted;
by origin;
run;
data last;
set sorted;
by origin;
if last.origin;
run;
proc print data = last;
run;

* task 3: find the maximum weight and length for each origin;
* method 1: using sort + last / first;
proc sort data = subset out = sorted2;
by origin descending weight descending length;
run;
data d3_1;
set sorted2;
by origin;
if first.origin;
run;
proc print data = d3_1;
run;

* method 2: proc sql;
proc sql;
select
	origin,
	weight,
	length
from subset
group by origin
having weight = max(weight);
quit;

* method 3: nodupkey!! need two sort;
proc sort data = subset out = sorted3;
by origin descending weight length;
run;
proc sort data = sorted3 nodupkey;
by origin;
run;

proc print data = sorted3;
run;




/*2. PROC SQL*/
*------------------------------------------------------------------------------------------------------------------------------------;
* proc sql allows users to retrieve, summarize, join and sort data;
* is used to (1). generate reports and summary statistics (2). retrieve and combine data from tables
* (3). create tables, views and indexes (4). retrieve data from DBMS ;
/*PROC SQL allows you to combine the functionality of the DATA step and PROC step in a single step*/

* we use a subset of dataset cars in sashelp lib as an example;
data example;
set sashelp.cars;
keep make model type origin MSRP weight length;
run;
proc print data = example;
run;

proc sql;
select
	origin,
	avg(weight) as avg_weight,
	avg(length) as avg_length,
	avg(MSRP) as avg_msrp
from example
where type in ('SUV', 'Sports', 'Truck', 'Hybrid')
group by origin
having avg_weight <= 4000;
quit;


proc sql;
select
	make,
	origin,
	case
		when weight < 2500 then 'small'
		when weight between 2500 and 3500 then 'medium'
		else 'heavy'
	end as sizeOfcar
from example;
quit;


proc sql;
select
	make,
	origin,
	weight / length as ratio,
	/*use the CALCULATED keyword with the alias to inform PROC SQL that the value is calculated within the query*/
	msrp * calculated ratio as new
from example;
quit;


* calculate descriptive statistics by using GROUP BY;
proc sql;
select
	type,
	max(weight) as max_weight,
	max(length) as max_length
from example
group by type
order by type;
quit;


* find the type of cars with the maximum average weight;
proc sql;
select
	type
from
(select
	type,
	avg(weight) as avg_weight
from example
group by type
) as temp
order by temp.avg_weight desc;
quit;



* select data from multiple tables;
* inner join: select all rows from both tables as long as there is a match between the columns in both tables;
data data1;
set example;
keep make origin type weight;
run;

data data2;
set example;
keep make origin type length;
run;

proc sql feedback;
create table newd as
select d1.make, d1.origin, d1.type, d1.weight, d2.length
from data1 as d1
inner join data2 as d2
/*these keys might not be the primary, hence the results might not be what we preferred */
on d1.make = d2.make and d1.origin = d2.origin and d1.type = d2.type;
quit;


* outer join: returns all matching records from both tables whether or not the other table matches to it;
* left outer join: returns all rows from the left table, with the matching rows in the right table;
data data1;
set example;
keep make origin type weight;
run;

data data2;
set example;
where length > 200;
keep make origin type length;
run;

* 428 obs in data1 while 63 obs in data2;
proc sql;
create table left_join as
select d1.make, d1.origin, d1.type, d1.weight, d2.length
from data1 d1
left join data2 d2
on d1.make = d2.make and d1.origin = d2.origin and d1.type = d2.type;
quit;


* cartesian join;
proc sql;
create table data1 as
select distinct make, max(weight) as max_weight
from example
group by make;
quit;
* 38 obs;

proc sql;
create table data2 as
select distinct type, max(length) as max_len
from example
group by type;
quit;
* 6 obs;

proc print data = data1;
run;
proc print data = data2;
run;

proc sql;
create table cartesian_join as
select
	d1.make, d2.type
from data1 as d1, data2 as d2;
quit;

proc print data = cartesian_join;
run;
* 38 * 6 = 228 obs in cartesian_join dataset;

* concatenating tables using UNION operator;
proc freq data = example;
tables type;
run;

proc sql;
create table SUV as
select *
from example
where type = 'SUV';
quit;
* 60 obs in SUV dataset;

proc sql;
create table Truck as
select *
from example
where type = 'Truck';
quit;
*24 obs in Truck dataset;

proc sql;
create table output as
select Make, Model, Type, Origin, MSRP, Weight, Length
from SUV
UNION
select Make, Model, Type, Origin, MSRP, Weight, Length
from Truck;
quit;
/*UNION is somewhat different from SET in data step: UNION sorts the data by the first column while SET maintains the order of two raw data sets*/
* 84 obs in output;
proc print data = SUV;
run;

proc print data = Truck;
run;

proc print data = output;
run;


* projects: data manipulation + data visualization;
*------------------------------------------------------------------------------------------------------------------------------------;
data project;
set sashelp.cars;
keep make model type origin MSRP weight length;
run;

* task 1: plot the relationship between weight and length by type and display them in a panel;
* weight by type;
proc sgpanel data = project;
panelby type / novarname spacing = 5;
scatter x = weight y = length;
run;

* task 2: plot the bar chart shows the freq in each origin in each type;
proc sgplot data = project;
vbar type / group = origin groupdisplay = cluster;
label type = 'different types of car' ;
title 'Number of cars/ types from different origins';
run;

title;

proc sgplot data = project;
vbar origin / group = type groupdisplay = cluster;
label origin = 'different origins' ;
title 'Number of cars/ origin from different types';
run;

title;


* task 3: Distribution of weight;
proc sgplot data = project;
histogram weight / binwidth = 2 nbins = 50 showbins scale = count;
density weight / type = kernel;
run;


* task 4: box plot of weight by different origins or types;
proc sgplot data = project;
vbox weight / category = type;
run;

proc sgplot data = project;
vbox weight / category = origin;
run;

* task 5: panel: the relationship between MSRP and weight for different origin;
proc sgpanel data = project;
panelby origin / novarname spacing = 5;
scatter x = weight y = MSRP;
run;
