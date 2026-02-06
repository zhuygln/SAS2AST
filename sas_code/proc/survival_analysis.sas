/***********************************************************************
 * Source: SAS-master (GitHub)
 *
 * Included as test fixture for sas2ast parser project.
 ***********************************************************************/

/*survival project*/
* source: ucla;

/*1. background:
Survival analysis models factors that influence the time to event.
OLS regression fails because
(1). the time to event is typically not normally distributed. (2). it cannot handle censoring which is very common in survival data.
*/


* 2. load data and introduction to data;
proc format;
value gender 1 = 'female' 0 = 'male';
run;
data data;
set Tmp1.Whas500;
format gender gender.;
run;
proc print data = data (obs = 10);
run;

/*Introduction to data
500 subjects of the Worcester Heart Attack study (hence data set is called WHAS500)
this study examined several factors, such as age, gender adn BMI, that may influence survival time after heart attack.
Follow up time for all subjects begins at the time of hospital admission after heart attack and ends with death or loss to follow up (censoring)

The variables used in this study:
'lenfol': length of follow-up, terminated either by death or censoring (The outcome in this study);
'fstat': the censoring variable, loss to follow-up = 0, death = 1;
'age': age at hospitalization;
'bmi': body mass index;
'hr': initial heart rate;
'gender': male = 0, female = 1;

The data are subject to right censor only: for some subjects we do not know when they died after heart attack,
but we do know at least how many days they survived.
*/



/*3. Distributions in survival analysis */
* The probability density function, f(t) describes likelihood of observing TIME at time t relative to all other survival times;
* removed all censored observations to help presentation and explanation;
proc univariate data = data(where = (fstat=1));
var lenfol;
histogram lenfol / kernel;
run;

* The cumulative distribution function, F(t): describes the probability of observing TIME <= some time t;
proc univariate data = data(where = (fstat=1));
var lenfol;
cdfplot lenfol;
run;


* The survival function, S(t) = 1 - F(t) describes the probability of surviving past time t, Pr(Time > t) ;
* using PROC LIFETEST to graph S(t) , the option atrisk is to display the number at risk in our sample at various time points;
proc lifetest data = data plots = survival(atrisk) CS = '+';
* the variable before '*' tells SAS the event time variable. (0) tells SAS which values are censored;
time lenfol * fstat(0);
run;

* Hazard function or hazard rate h(t) = f(t) / S(t) describes the relative likelihood of the event occuring at time t (f(t)),
conditional on the subject's survival up to that time t (S(t)). The rate thus describes the instantaneous rate of failure at time t and
ignores the accumulation of hazard up to time t (unlike F(t) and S(t));
proc lifetest data = data(where = (fstat=1)) plots = hazard(bw=200);
time lenfol * fstat(0);
run;


/*4. Data exploration*/
proc corr data = data plots(maxpoints = none) = matrix(histogram);
var lenfol gender age bmi hr;
run;



/*5. Nonparametric method:
in SAS, LIFETEST provides the methods for nonparametric test. e.g.
(1).Kaplam-Meier to estimate survival probability
(2).log-rank test to deal with the grouped test;
this procedure is mainly used to estimate the survival function and do the univariate analysis
*/

/* Kaplam-Meier survival function estimator:
S_hat(t) =  prod_{ti <= t} (ni - di) / ni
where ni is the number of subjects at risk and di is the number of subjects who fail, both at time ti;
Thus, each term in the product is the conditional probability of survival beyond time ti, meaning the probability
of surviving beyond time ti, given the subject has survived beyond time ti!!!!!!!!!!!!!!!!!!!!!!
The survival probability of survival beyond time t (the probability of survival beyond time t from the onset of risk)
is then obtained by multiplying together these conditional probabilities up to time t together!!!

e.g.
For the first interval: from 1 day to just before 2 days, ni = 500, di = 8, so S_hat(1) = (500 - 8) / 500 = 0.984
For the second interval: from 2 days to just before 3 days during which another 8 people died, given that the subject
has survived 2 days (the conditional probability) is (492 - 8) / 492 = 0.98374; hence the unconditonal probability of
survival beyond 2 days (from the onset of risk) the is S_hat(2) = 0.984 * 0.98374 = 0.9680.
*/
proc lifetest data = data atrisk outs = output;
time lenfol * fstat(0);
run;

* graphing the K-M estimate;
* when a subject dies at a particular time point, the step fucntion drops, whereas in between failure times the graph remains flat;
proc lifetest data = data atrisk plots = survival(cb) outs = output2;
time lenfol * fstat(0);
run;


* comparing survival function using nonparametric tests;
* strata!!!!!!!!;
proc lifetest data = data atrisk plots = survival(atrisk cb) outs = output3;
strata gender;
time lenfol * fstat(0);
run;

/* From the output, we found 3 chi-square based tests of the equality of the survival function over strata.
The p-values provide us evidence of the difference  between genders, the statistic is
Q = (sum_{i=1}^m wj * (d_ij - e_hat_ij))^2 / (sum_{i=1}^m w_{ij}^2 * v_hat_ij)
where dij is the observed number of failures in stratum i at time tj, e_hat_ij is the expected number of failures in stratum i at time tj.
v_hat_ij is the estiamtor of the variance of d_ij, w_i is the weight of the difference at time tj.

Two nonparametric test:
log-rank test: wj = 1 i.e. equal weights for all time inetrvals;
Wilcoxon test: wj = nj i.e. weighted by the number at risk at time tj, thus gving more weights to differences that occur earlier in followup time.

One parametric test:
Likelihood ratio test: assuming exponentially distributed survival times;
*/



/* 6. Cox proportional model:
We attempt to estimate parameters which describe the relationship between our predictors and the hazard rate.
Suppose there are m factors that might affect the time to event T, and hi(t) is the hazard rate of the i-th subject at time t,
i.e. after time t, the hazard rate of immediate death;  h0(t) represents the hazard rate at time t without being affected by factors (baseline).
The model can be expressed as
hi(t) = h0(t) * exp(b1 * x_i1 + b2 * x_i2 + ...+ bm * x_im)
devided by h0(t) and take log:
log(hi(t) / h0(t)) = b1 * x_i1 + b2 * x_i2 + ...+ bm * x_im
hence the linear combinations of all factors is equal to the log of hazard ratio for the i-th subject

The ratio of harzrd rates between two groups with fixed covariates will stay constant over time
e.g. the hazard rate when time t when x = x1 would then be h(t|x1) = h0(t) * exp(x1*b)
at time t when x = x2 would be h(t|x2) = h0(t) * exp(x2*b). The covariate effect of x, the is the ratio between those two hazard rates, or
a hazard ratio (HR):
HR  = h(t|x2) / h(t|x1) = h0(t) * exp(x2*b) / (h0(t) * exp(x1*b)) = exp(b*(x2 - x1)), HR does not depend on time t.
*/


* a simple Cox regression model;
proc phreg data = data;
class gender;
model lenfol * fstat(0) = gender age;
run;

* results: no 'intercept' (absorbed in baseline hazard function) , 'gender' is not significant.  'age' is significant, with each year of age the hazard rate increases by 7% (0.06683), ->
HR = exp(0.06683) = 1.069 and it is a significant change! ;

proc phreg data = data plots = survival;
class gender;
model lenfol * fstat(0) = gender age;
run;
* the reference curve is: male at age 69.85;

* using baseline statement to generate survival plots by group!!;
proc format;
value gender 0 = 'male' '1' = 'female';
run;
data covs;
input gender age;
format gender gender.;
cards;
0 69.845947
1 69.845947
;
run;

proc phreg data = data plots(overlay) = survival;
class gender;
model lenfol * fstat(0) = gender age;
baseline covariates = covs out = base / rowid = gender;
run;


* intersection terms: expanding the model with more predictor effetcs
e.g. we may suspect the effect of age is different for each gender
;
proc phreg data = data;
format gender gender;
class gender;
* gender + age + age* gender + BMI + BMI^2 + HR ;
model lenfol * fstat(0) = gender|age bmi|bmi hr;
run;


* interpret effetcs by using hazardratio statement;
proc phreg data = data;
class gender;
model lenfol * fstat(0) = gender|age bmi|bmi hr;
* at tells SAS at whcih level of our other covariates to evaluate the Hazard Ratio;
hazardratio 'Effect of 1-unit change in age by gender' age / at(gender=ALL);
hazardratio 'Effect of gender across ages' gender / at(age=(0 20 40 60 80));
hazardratio 'Effect of 5-unit change in bmi across bmi' bmi / at(bmi= (15 18.5 25 30 40)) units = 5;
run;



/* Time-varying variable*/
proc phreg data = data;
format gender gender.;
class gender;
model lenfol * fstat(0) = gender|age bmi|bmi hr in_hosp;
if lenfol > los then in_hosp = 0;
else in_hosp = 1;
run;
