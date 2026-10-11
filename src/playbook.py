"""Playbook: specific sub-problems inside each issue, with a suggested first step.

This turns "Login is the #1 issue" into "forced logouts are 40% of login complaints;
first step: keep sessions alive across network drops". The sub-problems were found by
reading the most common phrases inside each category's complaints (Apr 2025 onward).

Edit freely: each entry is a few keywords (regular expressions, matched as whole words
on lowercased text) and a first step. The first matching sub-problem wins, so put the
more specific ones first. First steps are starting points for the owning team based on
what reviewers describe; they are not verified root causes.

"vague": True marks catch-all buckets ("not working") that are counted but never
suggested as the place to start.
"""

SUB_ISSUES = {
    "login": [
        {"id": "forced_logout", "name": "Forced logout / login every time",
         "keywords": [r"logged out", r"logs? (me )?out", r"logging (me )?out", r"log ?out (again|automatically|every|frequently)",
                      r"(login|log in|sign in|otp) (again|every ?time|every day|daily|repeatedly)",
                      r"every ?time (i |we )?(open|login|log in)", r"session (expired|timeout)", r"unauthori[sz]ed",
                      r"keeps? (asking|logging)", r"re-?login", r"logouting", r"requires? (a )?login",
                      r"(keep|stay) (us |me )?(logged|signed) in", r"log ?in each time", r"save (the )?login"],
         "action": "Keep users signed in: extend session/refresh-token lifetime, don't sign out on brief network "
                   "loss or after an app update. Check which release introduced it using the version column."},
        {"id": "registration", "name": "Can't register / user not found",
         "keywords": [r"not registered", r"register\w*", r"user not found", r"sign ?up", r"verify my (number|email)"],
         "action": "Tell users clearly when their number/email isn't registered by their employer, and who to "
                   "contact, instead of silently not sending an OTP."},
        {"id": "otp_not_received", "name": "OTP not received or slow",
         # after forced logout, almost every remaining OTP mention is about delivery
         "keywords": [r"otps?", r"verif\w*", r"(not|never) send\w*"],
         "action": "Measure OTP delivery success per channel (SMS vs email) and per telecom operator; add a "
                   "fallback channel and a 'resend' timer that actually works."},
        {"id": "cant_login", "vague": True, "name": "Can't log in (no detail given)",
         "keywords": [r"(unable|not able|can'?t|cannot|couldn'?t) (to )?(log ?in|sign ?in|login)\w*", r"log ?in (issue|problem)\w*",
                      r"(log ?in|login) (is )?not working"],
         "action": "Track login success rate per release in analytics; these vague reports usually share a cause "
                   "with the specific sub-problems above."},
    ],
    "stability": [
        {"id": "install_check", "name": "False 'not installed from Play Store' / rooted-device block",
         "keywords": [r"not (downloaded|installed) from", r"play ?store", r"rooted\w*", r"not compatible"],
         "action": "Review the app-integrity/installer check: it blocks users who did install from Play Store. "
                   "Log false positives and reword the message so users know what to do."},
        {"id": "network", "name": "Fails on mobile data / some Wi-Fi / offline",
         "keywords": [r"mobile data", r"wi-?fi", r"network", r"internet", r"offline", r"no signal", r"connectivity"],
         "action": "Retry instead of erroring on slow networks, test on major Indian ISPs, and cache trip details "
                   "(cab number, OTP, driver) so they work offline at the pickup point."},
        {"id": "not_opening", "name": "Won't open / stuck loading / blank screen",
         "keywords": [r"(not|never|won'?t|doesn'?t|unable to|can'?t) (open|load)\w*", r"not opening", r"loading",
                      r"blank", r"stuck", r"something went wrong", r"white screen", r"hang\w*", r"freez\w*"],
         "action": "Check startup crash and ANR rates per version in Android vitals / Crashlytics; fix the top "
                   "startup failure first."},
        {"id": "crash", "name": "Crashes / closes by itself",
         "keywords": [r"crash\w*", r"clos(es|ing) (automatically|itself|suddenly)", r"automatic(ally)? clos\w*", r"force clos\w*"],
         "action": "Prioritise the top crash clusters in Crashlytics by affected users; add crash-rate gates to "
                   "staged rollouts."},
        {"id": "after_update", "name": "Broke after an update",
         "keywords": [r"update\w*", r"new version", r"latest version"],
         "action": "Use staged rollouts (5% → 20% → 100%) and halt when crash or 1★ rate rises versus the previous "
                   "version."},
        {"id": "not_working", "vague": True, "name": "\"Not working\" (no detail given)",
         "keywords": [r"not working", r"(doesn'?t|does not|isn'?t|is not|never) work\w*", r"stopped working", r"useless",
                      r"bug\w*", r"glitch\w*", r"errors?"],
         "action": "Too vague to act on alone: watch whether this rises with a release, alongside crash/ANR rates."},
    ],
    "booking": [
        {"id": "no_show", "name": "Marked no-show unfairly",
         "keywords": [r"no[- ]?show\w*", r"marked (me )?absent"],
         "action": "Show the evidence behind a no-show (driver GPS at pickup, call attempts) and add an in-app "
                   "dispute button routed to the transport desk."},
        {"id": "cancel_edit", "name": "Can't cancel or change a booking",
         "keywords": [r"cancel\w*", r"edit\w*", r"modify", r"reschedul\w*", r"change (the |my )?(time|booking|schedule)"],
         "action": "Let users cancel/modify bookings in the app with a clear confirmation screen."},
        {"id": "booking_not_shown", "name": "Booked trip not visible / wrong schedule shown",
         "keywords": [r"(booking|booked|schedule|trip)s? (is |are )?not (show\w*|visible|reflect\w*|available)",
                      r"(can'?t|cannot|unable to) see (my )?(booking|schedule|trip)", r"duplicate", r"monthly view",
                      r"whole month"],
         "action": "Make 'My bookings' the single source of truth: show every upcoming trip (week/month view) "
                   "and sync with the roster."},
        {"id": "waitlist_capacity", "name": "Waitlist / seats full",
         "keywords": [r"wait ?list\w*", r"seats?", r"slots?", r"full"],
         "action": "Show waitlist position and the outcome clearly; share seat-shortage data with the transport desk."},
        {"id": "booking_fails", "name": "Booking fails or flow is confusing",
         "keywords": [r"(unable|not able|can'?t|cannot) (to )?(book|schedule)", r"book\w*", r"schedul\w*", r"roster\w*"],
         "action": "Instrument the booking funnel (start → submit → confirmed) to see where attempts fail; "
                   "compare against the previous one-step flow."},
    ],
    "tracking": [
        {"id": "eta_wrong", "name": "ETA wrong or jumps",
         "keywords": [r"eta", r"arrival", r"\d+ ?min\w*", r"timing\w*", r"time (is |was )?(wrong|incorrect|different)"],
         "action": "Compare shown ETA with actual pickup time per route; display 'updated x min ago' and avoid "
                   "showing ETAs when GPS data is stale."},
        {"id": "location_stale", "name": "Cab location wrong / not updating",
         "keywords": [r"location", r"gps", r"real ?-?time", r"not (moving|updat\w*)", r"hours? ago", r"same (place|point)"],
         "action": "Check the driver app's (Partner Lite) GPS upload frequency and gaps; show last-update time "
                   "on the cab icon."},
        {"id": "map_ux", "name": "Map zoom/view problems",
         "keywords": [r"zoom\w*", r"maps?", r"navigation"],
         "action": "Respect the user's zoom; focus the map on cab + pickup point before boarding."},
        {"id": "details_missing", "name": "Cab/driver details not shown",
         "keywords": [r"(cab|vehicle|car|driver) (number|details|info)", r"co-?passengers?"],
         "action": "Show cab number and driver details as soon as a cab is assigned, and keep them visible offline."},
    ],
    "prompts": [
        {"id": "policy_every_time", "name": "Accept transport policy every time",
         "keywords": [r"polic(y|ies)", r"terms", r"agreements?", r"accept\w*", r"i agree"],
         "action": "Store the accepted policy version; show it again only when it changes."},
        {"id": "forced_rating", "name": "Forced trip/app rating",
         "keywords": [r"rat(e|ing)", r"review", r"skip"],
         "action": "Make trip rating skippable and never block trip details behind it. Ask for a Play Store "
                   "rating only after a good trip, not after every ride."},
        {"id": "seat_belt", "name": "Seat-belt pop-up before OTP",
         "keywords": [r"seat ?belt"],
         "action": "Don't gate the boarding OTP behind the seat-belt pop-up; confirm it once at boarding."},
        {"id": "permissions", "name": "Too many permissions",
         "keywords": [r"permission\w*", r"bluetooth", r"timezone", r"sms"],
         "action": "Request only permissions needed for the current action and explain why."},
    ],
    "notifications": [
        {"id": "wrong_or_spam", "name": "Wrong, duplicate or unnecessary alerts",
         "keywords": [r"unnecessary", r"too many", r"spam", r"wrong", r"ghost", r"even (after|when|though)", r"irritat\w*"],
         "action": "Audit notification triggers (e.g. alerts about other passengers' boarding); dedupe and add "
                   "per-type settings."},
        {"id": "missing_late", "name": "Missing or late alerts",
         "keywords": [r"(not|never) (receiv\w*|get|getting|com\w*)", r"delay\w*", r"late"],
         "action": "Track push delivery rate and latency; fall back to SMS for pickup-critical alerts."},
    ],
    "cab_delay": [
        {"id": "no_show", "name": "Marked no-show unfairly",
         "keywords": [r"no[- ]?show\w*", r"marked (me )?absent", r"didn'?t wait", r"don'?t (even )?wait"],
         "action": "Require a driver call attempt and GPS proof at the pickup point before a no-show can be marked."},
        {"id": "late", "name": "Cab late / never came",
         "keywords": [r"late", r"delay\w*", r"on time", r"never (came|come)", r"wait\w*"],
         "action": "Share weekly punctuality by vendor and route with the client transport desk; flag chronic routes."},
    ],
    "routing": [
        {"id": "pickup_point", "name": "Pickup points far or removed",
         "keywords": [r"pick ?-?up (point|location)s?", r"nodal\w*", r"walk\w*", r"far", r"stops?", r"boarding points?"],
         "action": "Review pickup-point distance rules with the client transport desk; publish a max walking distance."},
        {"id": "long_route", "name": "Long routes / bad pooling",
         "keywords": [r"rout(e|es|ing)", r"long", r"hours?", r"pooling", r"club\w*", r"sequence"],
         "action": "Cap maximum ride time per employee and audit outlier routes from the routing engine."},
    ],
    "support": [
        {"id": "contact_driver", "name": "Can't call or chat with the driver",
         "keywords": [r"(call|contact|connect|reach|chat)\w*.{0,20}driver", r"driver.{0,15}(number|contact)",
                      r"call(ing)? (option|permission)", r"calls? (are )?not connect\w*"],
         "action": "Restore masked calling or add in-app chat between employee and driver for the trip window."},
        {"id": "no_feedback", "name": "No way to give feedback / report a problem",
         "keywords": [r"feedback\w*", r"rate (the )?driver", r"driver rating", r"report\w*"],
         "action": "Add in-app 'Report a problem' with ticket status, so complaints reach ops instead of the Play Store."},
        {"id": "helpdesk", "name": "Helpdesk unresponsive",
         "keywords": [r"help ?desk", r"support", r"no response", r"complain\w*", r"escalat\w*"],
         "action": "Track helpdesk response time and resolution rate; publish an SLA."},
    ],
    "usability": [
        {"id": "new_ui_worse", "name": "New design worse than the old one",
         "keywords": [r"(old|previous|earlier) (app|version|ui)", r"new (ui|design|update|version|app)", r"removed"],
         "action": "Usability-test the new flows against the old ones; restore removed features people miss."},
        {"id": "dark_mode", "name": "No dark mode",
         "keywords": [r"dark (mode|theme)"],
         "action": "Support the system dark mode (many people check the app early morning or late night)."},
        {"id": "not_friendly", "name": "Hard to use / confusing",
         "keywords": [r"user ?-?friendly", r"confus\w*", r"difficult", r"complicated", r"too many (taps|clicks|steps)"],
         "action": "Run a 5-user usability test on booking and tracking; fix the top three drop-off points."},
    ],
}
