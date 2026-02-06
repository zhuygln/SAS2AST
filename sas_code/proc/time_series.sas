/***********************************************************************
 * Source: SAS-master (GitHub)
 *
 * Included as test fixture for sas2ast parser project.
 ***********************************************************************/

/*examples in time series*/

data example1;
input price;
time = intnx('month', '01jan2006'd, _n_-1);
format time monyy.;
cards;
3.41
3.54
3.42
3.53
3.45
;
run;

proc print data = example1;
run;

/*log transformation*/
data example2;
input price;
logprice = log(price);
time = intnx('month', '01jan2006'd, _n_-1);
format time monyy.;
cards;
3.41
3.45
3.42
3.53
3.45
;
run;
proc print data = example2;
run;

/*subset of data*/
data sub;
set example2;
keep time logprice;
where time >= '01mar2006'd;
run;

proc print data = sub;
run;


/*missing data imputation*/
data example4;
input price;
time = intnx('month', '01jan2006'd, _n_+1);
format time date.;
cards;
3.41
3.45
.
3.53
3.45
;
run;
proc expand data = example4 out = complete;
id time;
proc print data = example4;
proc print data = complete;
run;


/*draw time series plots*/
data example;
input price1 price2;
time = intnx('month', '01jan2005'd, _n_-1);
format time date.;
cards;
12.85 15.21
13.29 14.23
12.41 14.69
15.21 13.27
14.23 16.75
13.56 15.33
;
proc gplot data = example;
plot price1*time = 1 price2*time = 2 / overlay;
symbol1 c = black v = star i = join;
symbol2 c = red v = circle i = spline;
run;


/*stationary test*/
data example;
input freq@@;
year = intnx('year', '01jan1970'd, _n_-1);
format year year4.;
cards;
97 154 137.7 149 164 157 188 204 179 210 202 218 209
204 211 206 214 217 210 219 211 233 316 221 239
215 228 219 239 224 234 227 298 332 245 357 301 389
;

proc arima data = example;
identify var = freq;
run;


/*random test*/
data a;
do time = 50 to 1000 by 1;
noise = rannor(123);
if time > 0 then output;
end;

proc gplot;
plot noise * time;
symbol v = none i = join c = red;

proc arima data = a;
identify var = noise;
run;


/*fit a linear trend*/
data example;
input x@@;
t = _n_;
cards;
12.79 14.02 12.92 18.27 21.22 18.81
25.73 26.27 26.75 28.73 31.71 33.95
;
run;
proc arima data = example;
identify var = x;
run;
proc autoreg data = example;
model x  = t;
run;


/*nonlinear trend fit*/
data nonlinear;
input x@@;
t = _n_;
cards;
1.85 7.48 14.29 23.02 37.42 74.27 140.72
265.81 528.23 1040.27 4113.73 8212.21 16405.95
;

proc gplot data = nonlinear;
plot x*t;
symbol c = red v = none i = join;
run;

/*gauss-iterative method, other methods: newton, grandient */
proc nlin method = gauss;
model x = a*t + b ** t;
/*define estimated parameters and initialize these parameters*/
parameters a = 0.1 b=1.1;
/*forst derivatives in terms of a and b*/
der.a = t;
der.b = t * b ** (t-1);
/*output results into a new dataset: out, out contains t, x nd xhat (fitted value) */
output predicted=xhat out =out;
run;

/*comapre the original plot and the fitted plot*/
proc gplot data = out;
plot x*t = 1 xhat*t=2 / overlay;
symbol1 c = black i = none v = star;
symbol2 c = red i = join v = none;
run;


/*fit arima model
ARMA model is a special case of ARIMA model. Both of them are in the proc ARIMA
*/
data example5;
input x@@;
difx = dif(x);
t = _n_;
cards;
1.05 -0.84 -1.42 0.20 2.81 6.72 5.40 4.38
5.52 4.46 2.89 -0.43 -4.86 -8.54 -11.54 -16.22
-19.41 -21.64 -22.51 -23.51 -24.49 -25.54 -24.06 -23.44
-23.41 -24.17 -21.58 -19.00 -14.14 -12.69 -9.48 -10.29
-9.88 -8.33 -4.67 -2.97 -2.91 -1.86 -1.91 -0.80
;
proc gplot;
plot x*t;
symbol v=star c=black i = join;
run;

proc gplot;
plot difx * t;
run;

proc arima data = example5;
identify var=x(1);
estimate p = 1;
forecast lead = 5 id = t;
run;


/*example of fitting auto-regression model*/
/*step1: create data set and draw time-series plot*/
data example2;
input x@@;
t = _n_;
cards;
3.03 8.46 10.22 9.80 11.96 2.83
8.43 13.77 16.18 16.84 19.57 13.26
14.78 24.48 28.16 28.27 32.62 18.44
25.25 38.36 43.70 44.46 50.66 33.01
39.97 60.17 68.12 68.74 78.15 49.84
62.23 91.49 103.2 104.53 118.18 77.88
94.75 138.36 155.68 157.46 177.69 117.15
;

proc gplot;
plot x*t;
symbol c=black i = join v=star;
run;


/*step2: bulid a time-dependent model*/
proc autoreg data = example2;
/*t is the independent variable and x is the dependent variable, we build a linear model:
x_t = a + bt + u_t, where {u_t} is the residual series;*/
model x = t / dwprob;
run;

/*we focus on the result of D-W(Durbin-Watson) test
and found that the statistic of DW test is 0.7628 > 0 and p-value < 0.01
which represents that the residuals are significally positive correlated.
hence we should fit autoregression model for the residuals
*/

/*step3: fit autogression model for residuals*/
proc autoreg data = example2;
/*x_t = a + b*t + u_t,
where u_t = -r1*u_{t-1} - r2*u_{t-2} - r3*u_{t-3} - ... - r4*u_{t-5} + epsilon_t*/
model x = t / nlag = 5 backstep method=ml;
/*backstep is use to pick parameters that are significant; ml: use Maximum likelihood method to estimate parameters*/
run;

/*
based on the report of Backward Elimination of Autoregressive Terms: we found that only the 1st lag term is significant, so we
delete the rest of lag terms, and got the estimation of 1st lag term: phi_1 = - 0.603.
So u_t = 0.603*u_{t-1} + epsilon_t
*/



/*step4: fit the final model*/
proc autoreg data = example2;
model x = t / nlag=5 backstep method = ml noint;
/* the results that we want to output are
(1). P option: the estimation of paraemters; (2). PM option: the fitted value of linear trend */
output out = out p = xp pm = trend;
run;

/*the final model can be expressed as:
x_t = 2.76 * t + u_t
u_t = 0.688 * u_{t-1} + epsilon_t
epsilon_t i.i.d. ~ N(0, 250.9)
*/


/*step5: visualize*/
proc gplot data = out;
plot x*t = 2 xp*t=3 trend*t = 4/overlay;
symbol2 v = star i = none c = black;
symbol3 v = none i = join c = red w =2 l = 3;
symbol4 v = none i = join c = green w = 2;
run;


/*fit a dependent-lagged mdoel*/
data example2_lag;
input x@@;
t = _n_;
lagx = lag(x);
cards;
3.03 8.46 10.22 9.80 11.96 2.83
8.43 13.77 16.18 16.84 19.57 13.26
14.78 24.48 28.16 28.27 32.62 18.44
25.25 38.36 43.70 44.46 50.66 33.01
39.97 60.17 68.12 68.74 78.15 49.84
62.23 91.49 103.2 104.53 118.18 77.88
94.75 138.36 155.68 157.46 177.69 117.15
;
proc autoreg data = example2_lag;
model x = lagx / lagdep = lagx noint;
output out = out p = xp;
run;

proc gplot data = out;
plot x*t = 2 xp*t = 3 / overlay;
symbol2 v=star i=none c=black;
symbol3 v=none i=join c=red w=2;
run;
