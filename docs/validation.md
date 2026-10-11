# Classifier validation (held-out set)

100 random substantive 1-3 star reviews (Oct 2024 onward) not used to design keywords. Reference labels by Claude, independent of the Gemini labels; spot-check before quoting.

| method      | primary_exact   | primary_or_secondary   | left_unclassified   |   n |
|:------------|:----------------|:-----------------------|:--------------------|----:|
| Rules only  | 63%             | 77%                    | 19%                 | 100 |
| Rules + LLM | 75%             | 90%                    | 4%                  | 100 |

Reference labels: 95 specific, 5 vague.

Disagreements (reference -> predicted [source]):
     cab_delay -> routing      [rule] Non sense application, whenever we are the location to pick the cab after some time it sho
     cab_delay -> booking      [llm] Very pathetic system. If by any chance you miss cab, they wont alot cab even if it is urge
       support -> tracking     [rule] No option to connect to driver, either any chat option should be included so that driver a
       routing -> booking      [rule] Things are getting worse each day. Stuffing 7 people in a car to save money, especially fo
     cab_delay -> booking      [rule] Not sure if it's a location specific issue but I often don't get cabs even though I book i
     usability -> support      [rule] no provision for feedback on completed trips
     stability -> support      [rule] Network issues, always lagging and worst customer support.
     usability -> prompts      [llm] not able to rate the trip
     stability -> safety       [rule] Stop updating this app frequently... always got stuck in an emergency...
       booking -> routing      [rule] worst app, so many glitches and it is not accepting source or boarding points
         login -> stability    [rule] App logout if internet connection is not available for a moment and switched. also app sho
       support -> tracking     [rule] worst transport team just waste your time in case of real time cab and align only to those
     usability -> support      [rule] The worst app ever , App should be like EFMFM app simple and Accessible , there should be 
     stability -> login        [rule] The Move In Sync app crashes frequently, making it unreliable for daily use. App stability
         other -> booking      [rule] Worst cab app booking of the century
     cab_delay -> usability    [rule] very poor experience of pick up the timings change randomly every half n hour before pick 
       booking -> login        [rule] unable to approve any adhoc request and also very confusing application while you have to 
     cab_delay -> booking      [rule] service is extremely bad, better to take uber or rapido, no flexibility. driver don't even
         login -> safety       [rule] Keeps logging out after every 5 to 10 mins of inactivity on the app. Logging in again requ
      tracking -> support      [rule] This application is a disaster. Worst application ever. this application does not show the
       support -> driver       [rule] Total waste of time. Support is useless and the staff is incredibly rude. To make matters 
       routing -> booking      [llm] employees cab timing allotment can be better
     cab_delay -> booking      [rule] Worst service I've ever experienced. I wish I could give 0 stars—they deserve -10000. My l
     stability -> login        [rule] not able to open the app, automatic close in a sec. otp in mobile mail is not received. ho
     usability -> routing      [rule] worst app, no feedback option for routing and journey.
