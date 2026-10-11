# Rule classifier evaluation (v1)

Output of `python -m scripts.evaluate_rules`. Note: the manual labels were also used to design the keywords, so the agreement numbers are optimistic. A separate validation set is planned for M5.

```
1-3 star reviews: 8,607
  low info / no text:   1,267 (14.7%)
  unclassified (Other): 1,732 = 23.6% of substantive reviews

Primary category share (substantive 1-3 star reviews):
  Other / unclassified                  1,732   23.6%
  Tracking, ETA and map                 1,414   19.3%
  Booking and schedule                    955   13.0%
  App stability and performance           954   13.0%
  Login, OTP and session                  683    9.3%
  Routing and pickup points               411    5.6%
  Usability and design                    284    3.9%
  Support and contact                     270    3.7%
  Notifications                           172    2.3%
  Cab late or no-show                     153    2.1%
  Repeated prompts and permissions        119    1.6%
  Safety concern                           85    1.2%
  Driver behaviour                         63    0.9%
  Vehicle and vendor quality               45    0.6%

Last 12 months: unclassified = 21.5% of 731 substantive 1-3 star reviews

Agreement with manual labels (94 reviews with a specific theme):
  primary category matches manual theme: 68%
  manual theme among matched categories: 88%
  rules found nothing:                   2%
  manually 'vague' reviews: 6; rules left 3 of them unclassified

Misses (manual theme not found by rules):
  [      booking | rules: stability] it doesn't work properly, it gives Saturday Sunday also shuttle, which it doesn't give in realy
  [      booking | rules: cab_delay] it always allocates the trip early and doest give any details of previous trip details. pathetic it is.
  [    usability | rules: tracking] it's too hectic to update the new location.
  [    cab_delay | rules: -] very worst service. Not even a single day the cab picked up....
  [    usability | rules: routing|tracking] worst app ever for first time users, they don't mention clear instructions that you need to goto a pickup loca
  [      prompts | rules: login] we have to give otp everytime to the driver
  [    stability | rules: support] Multiple issues have been observed following the recent updates. The matter has already been reported to our o
  [       safety | rules: prompts|support] I'm getting calling permission is disabled as per company policy
  [     tracking | rules: -] Worthless app..Driver arrival shows in 5mins when we leave home to the pick point changes to 30mins..I mean ch
  [      routing | rules: booking|cab_delay|support] works well overall, but they don't listen to feedback. for example, pick ups from same apartment complex are s
  [    cab_delay | rules: vehicle_vendor] super bad service with bad transport management. Company should release these transport vendors.
```
