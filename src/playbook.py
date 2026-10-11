"""Playbook: the specific problems inside each issue, each with an action card.

This turns "Login is the #1 issue" into "43% of login complaints are OTPs not arriving;
here is who should do what, how hard it is, and how we'll know it worked".

The specific problems were found by reading the most common phrases inside each issue's
complaints (Apr 2025 onward). Each entry has:

  keywords     whole-word patterns (lowercase); the first matching problem wins, so the
               more specific ones come first
  action       what to do, in plain words
  owner        which team should pick it up
  effort       1–5, see EFFORT below (a judgement call; edit freely)
  measure      the number in MoveInSync's own systems that should move if the fix works
  check_first  what to look at internally before building anything, to confirm the cause

Actions are starting points based on what reviewers describe, not proven root causes.
"vague": True marks catch-all buckets ("not working") that are counted but never
suggested as the place to start.
"""

EFFORT = {
    1: "A setting or wording change (days)",
    2: "A small change (about a week)",
    3: "About one sprint (2 weeks)",
    4: "Several sprints or two teams",
    5: "A big project, or mostly outside the app",
}

# How "did it work?" is answered for every card: the team's own number (measure) plus,
# from the outside, this dashboard's Fix tracker (complaints per 100 reviews before vs after).
VERIFY_FROM_REVIEWS = "the Fix tracker in this dashboard should show fewer complaints about this per 100 reviews."

SUB_ISSUES = {
    "login": [
        {"id": "forced_logout", "name": "Logged out too often / must log in every time",
         "keywords": [r"logged out", r"logs? (me )?out", r"logging (me )?out", r"log ?out (again|automatically|every|frequently)",
                      r"(login|log in|sign in|otp) (again|every ?time|every day|daily|repeatedly)",
                      r"every ?time (i |we )?(open|login|log in)", r"session (expired|timeout)", r"unauthori[sz]ed",
                      r"keeps? (asking|logging)", r"re-?login", r"logouting", r"requires? (a )?login",
                      r"(keep|stay) (us |me )?(logged|signed) in", r"log ?in each time", r"save (the )?login"],
         "action": "Keep people signed in. Make the login session last longer, renew it quietly in the background, "
                   "and don't sign people out when the network drops for a moment or after an app update.",
         "owner": "Mobile app team + login/backend team", "effort": 3,
         "measure": "Forced logouts per active user per week; share of app opens that start on the login screen",
         "check_first": "Session-expiry and token-renewal logs: how long sessions really last, and which app "
                        "version started logging people out"},
        {"id": "registration", "name": "Can't register / \"user not found\"",
         "keywords": [r"not registered", r"register\w*", r"user not found", r"sign ?up", r"verify my (number|email)"],
         "action": "When a phone number or email isn't registered by the employer, say so clearly and tell the user "
                   "who to contact, instead of silently not sending an OTP.",
         "owner": "Mobile app team + customer success (employer onboarding)", "effort": 2,
         "measure": "Login attempts that fail with \"user not found\"; tickets about registration",
         "check_first": "How many login attempts come from numbers/emails not in any employer's list"},
        {"id": "otp_not_received", "name": "OTP not received or slow",
         # after forced logout, almost every remaining OTP mention is about delivery
         "keywords": [r"otps?", r"verif\w*", r"(not|never) send\w*"],
         "action": "Find out where OTPs get lost: measure delivery by channel (SMS, email) and by mobile operator. "
                   "Add a backup channel, read the SMS code automatically, and make \"resend\" work reliably.",
         "owner": "Mobile app team + SMS/OTP provider", "effort": 3,
         "measure": "OTP delivery success rate; median time from request to login; how often users tap \"resend\"",
         "check_first": "OTP send/deliver/verify logs and the SMS provider's delivery report, split by operator"},
        {"id": "cant_login", "vague": True, "name": "Can't log in (no detail given)",
         "keywords": [r"(unable|not able|can'?t|cannot|couldn'?t) (to )?(log ?in|sign ?in|login)\w*", r"log ?in (issue|problem)\w*",
                      r"(log ?in|login) (is )?not working"],
         "action": "Too vague to act on alone. Track the login success rate per app version; these reports usually "
                   "share a cause with the specific login problems above.",
         "owner": "Mobile app team", "effort": 2,
         "measure": "Login success rate per app version",
         "check_first": "Login funnel: how many people who start logging in actually get in"},
    ],
    "stability": [
        {"id": "install_check", "name": "Blocked by a wrong \"not installed from Play Store\" / rooted-phone check",
         "keywords": [r"not (downloaded|installed) from", r"play ?store", r"rooted\w*", r"not compatible"],
         "action": "The app's security check blocks people who did install it from the Play Store. Find the false "
                   "alarms, fix the check, and rewrite the message so users know what to do.",
         "owner": "Mobile app team (security)", "effort": 2,
         "measure": "How often the security check blocks a user, and how many of those were genuine installs",
         "check_first": "Logs of the integrity/root check: which phones and app versions it blocks"},
        {"id": "network", "name": "Fails on mobile data / some Wi-Fi / no signal",
         "keywords": [r"mobile data", r"wi-?fi", r"network", r"internet", r"offline", r"no signal", r"connectivity"],
         "action": "Retry quietly instead of showing an error on weak networks, test on the main Indian mobile "
                   "networks, and keep trip details (cab number, OTP, driver) on the phone so they work without signal "
                   "at the pickup point.",
         "owner": "Mobile app team", "effort": 3,
         "measure": "Share of app sessions with a network error, by mobile operator",
         "check_first": "Error logs by network type and operator; which screens fail without signal"},
        {"id": "not_opening", "name": "Won't open / stuck loading / blank screen",
         "keywords": [r"(not|never|won'?t|doesn'?t|unable to|can'?t) (open|load)\w*", r"not opening", r"loading",
                      r"blank", r"stuck", r"something went wrong", r"white screen", r"hang\w*", r"freez\w*"],
         "action": "Look at the crash and \"app not responding\" reports for app start-up, by app version, and fix the "
                   "most common failure first.",
         "owner": "Mobile app team", "effort": 3,
         "measure": "Share of app opens that fail or freeze; start-up time",
         "check_first": "Play Console \"Android vitals\" (crashes, app-not-responding) for the start-up screen"},
        {"id": "crash", "name": "Crashes / closes by itself",
         "keywords": [r"crash\w*", r"clos(es|ing) (automatically|itself|suddenly)", r"automatic(ally)? clos\w*", r"force clos\w*"],
         "action": "Fix the crashes that affect the most users first, and stop a new release from going to everyone "
                   "if its crash rate rises.",
         "owner": "Mobile app team", "effort": 3,
         "measure": "Crash-free sessions (aim for 99.5% or more)",
         "check_first": "Crash reports grouped by cause, phone model and app version"},
        {"id": "after_update", "name": "Broke after an update",
         "keywords": [r"update\w*", r"new version", r"latest version"],
         "action": "Release new versions in steps (5% of users, then 20%, then everyone) and pause if crashes or 1★ "
                   "reviews rise compared with the previous version.",
         "owner": "Mobile app team + release management", "effort": 2,
         "measure": "Crash rate and 1★ share of each new version vs the previous one",
         "check_first": "Release history against crash rates; the version chart in this dashboard"},
        {"id": "not_working", "vague": True, "name": "\"Not working\" (no detail given)",
         "keywords": [r"not working", r"(doesn'?t|does not|isn'?t|is not|never) work\w*", r"stopped working", r"useless",
                      r"bug\w*", r"glitch\w*", r"errors?"],
         "action": "Too vague to act on alone. Watch whether it rises with a release, alongside crash rates.",
         "owner": "Mobile app team", "effort": 2,
         "measure": "Error rate per app version",
         "check_first": "Whether spikes line up with release dates"},
    ],
    "booking": [
        {"id": "no_show", "name": "Marked \"no-show\" unfairly",
         "keywords": [r"no[- ]?show\w*", r"marked (me )?absent"],
         "action": "Show the employee the evidence behind a no-show (where the cab was, whether the driver called) "
                   "and add a \"dispute this\" button that goes to the transport desk.",
         "owner": "Product + operations (transport desk)", "effort": 3,
         "measure": "No-show disputes raised and overturned",
         "check_first": "No-shows where the driver's GPS was not at the pickup point or no call was made"},
        {"id": "cancel_edit", "name": "Can't cancel or change a booking",
         "keywords": [r"cancel\w*", r"edit\w*", r"modify", r"reschedul\w*", r"change (the |my )?(time|booking|schedule)"],
         "action": "Let people cancel or change a booking in the app, with a clear confirmation screen, and show the "
                   "employer's cut-off time before they try.",
         "owner": "Product + mobile app team", "effort": 3,
         "measure": "Share of cancel/change attempts that succeed",
         "check_first": "Failed cancel/edit requests and their error reasons; employer cut-off settings"},
        {"id": "booking_not_shown", "name": "Booked trip not visible / wrong schedule shown",
         "keywords": [r"(booking|booked|schedule|trip)s? (is |are )?not (show\w*|visible|reflect\w*|available)",
                      r"(can'?t|cannot|unable to) see (my )?(booking|schedule|trip)", r"duplicate", r"monthly view",
                      r"whole month"],
         "action": "Make \"My bookings\" always correct and complete: show every upcoming trip (week and month view), "
                   "in sync with the roster.",
         "owner": "Mobile app team + backend team", "effort": 3,
         "measure": "Mismatches between the app's booking list and the roster",
         "check_first": "Compare app booking lists with roster data for a sample of users"},
        {"id": "waitlist_capacity", "name": "Waitlisted / seats full",
         "keywords": [r"wait ?list\w*", r"seats?", r"slots?", r"full"],
         "action": "Show the user their waitlist position and the final outcome clearly, and share seat shortages "
                   "with the employer's transport desk.",
         "owner": "Product + operations", "effort": 2,
         "measure": "Waitlisted bookings that never get a seat",
         "check_first": "Waitlist outcomes by route and shift"},
        {"id": "booking_fails", "name": "Booking fails or the steps are confusing",
         "keywords": [r"(unable|not able|can'?t|cannot) (to )?(book|schedule)", r"book\w*", r"schedul\w*", r"roster\w*"],
         "action": "Measure each step of booking (open → choose → confirm → booked) to see where people give up or "
                   "hit errors, and compare with the older one-step flow users say was easier.",
         "owner": "Product + mobile app team", "effort": 3,
         "measure": "Booking completion rate (started vs confirmed)",
         "check_first": "Booking funnel drop-off and booking errors by app version"},
    ],
    "tracking": [
        {"id": "eta_wrong", "name": "Arrival time (ETA) wrong or jumps",
         "keywords": [r"eta", r"arrival", r"\d+ ?min\w*", r"timing\w*", r"time (is |was )?(wrong|incorrect|different)"],
         "action": "Compare the arrival time shown with the real pickup time, route by route. Show \"updated 2 min "
                   "ago\" next to the time, and don't show a time when the cab's location is out of date.",
         "owner": "Mobile app team + maps/tracking team", "effort": 4,
         "measure": "Average gap between shown and actual arrival time (minutes)",
         "check_first": "Predicted vs actual pickup times for a sample of trips"},
        {"id": "location_stale", "name": "Cab location wrong / not updating",
         "keywords": [r"location", r"gps", r"real ?-?time", r"not (moving|updat\w*)", r"hours? ago", r"same (place|point)"],
         "action": "Check how often the driver's app (Partner Lite) sends its location and where it stops sending. "
                   "Show the time of the last update on the cab icon.",
         "owner": "Maps/tracking team + driver app team", "effort": 3,
         "measure": "Age of the cab's last location update when employees look at the map",
         "check_first": "Gaps in driver GPS updates by vendor, phone and network"},
        {"id": "map_ux", "name": "Map zoom/view problems",
         "keywords": [r"zoom\w*", r"maps?", r"navigation"],
         "action": "Keep the user's zoom instead of resetting it, and before boarding focus the map on the cab and the "
                   "pickup point only.",
         "owner": "Mobile app team", "effort": 2,
         "measure": "Map-related complaints",
         "check_first": "Session recordings of the tracking screen"},
        {"id": "details_missing", "name": "Cab/driver details not shown",
         "keywords": [r"(cab|vehicle|car|driver) (number|details|info)", r"co-?passengers?"],
         "action": "Show the cab number and driver details as soon as a cab is assigned, and keep them visible "
                   "without signal.",
         "owner": "Mobile app team", "effort": 2,
         "measure": "Trips where the cab details weren't shown before pickup",
         "check_first": "Time between cab assignment and details appearing in the app"},
    ],
    "prompts": [
        {"id": "policy_every_time", "name": "Must accept the transport policy every time",
         "keywords": [r"polic(y|ies)", r"terms", r"agreements?", r"accept\w*", r"i agree"],
         "action": "Remember that the user accepted the policy. Show it again only when the policy changes.",
         "owner": "Mobile app team", "effort": 1,
         "measure": "Policy screens shown per user per week",
         "check_first": "Whether acceptance is stored per user and policy version"},
        {"id": "forced_rating", "name": "Forced to rate the trip or the app",
         "keywords": [r"rat(e|ing)", r"review", r"skip"],
         "action": "Make the trip rating skippable and never hide trip details behind it. Ask for a Play Store review "
                   "only after a good, on-time trip, not after every ride, and never ask \"do you like the app?\" "
                   "first (Google doesn't allow that).",
         "owner": "Product + mobile app team", "effort": 1,
         "measure": "Rating screens skipped; complaints about forced rating",
         "check_first": "When and how often rating and review prompts are shown today"},
        {"id": "seat_belt", "name": "Seat-belt pop-up before showing the OTP",
         "keywords": [r"seat ?belt"],
         "action": "Don't put the seat-belt pop-up in front of the boarding OTP. Ask once, at boarding.",
         "owner": "Product (safety) + mobile app team", "effort": 1,
         "measure": "Taps needed to see the OTP",
         "check_first": "Boarding flow: how many screens before the OTP"},
        {"id": "permissions", "name": "Asks for too many permissions",
         "keywords": [r"permission\w*", r"bluetooth", r"timezone", r"sms"],
         "action": "Ask only for the permissions the current screen needs, and say why in one line.",
         "owner": "Mobile app team", "effort": 2,
         "measure": "Permission requests per session; how often users say no",
         "check_first": "List of permissions requested and when"},
    ],
    "notifications": [
        {"id": "wrong_or_spam", "name": "Wrong, repeated or unnecessary alerts",
         "keywords": [r"unnecessary", r"too many", r"spam", r"wrong", r"ghost", r"even (after|when|though)", r"irritat\w*"],
         "action": "Review what triggers each alert (for example, alerts about other passengers boarding), remove "
                   "duplicates, and let users turn off non-essential ones.",
         "owner": "Mobile app team + product", "effort": 2,
         "measure": "Alerts per user per trip; alerts sent at the wrong time",
         "check_first": "Alert log against trip events"},
        {"id": "missing_late", "name": "Alerts missing or late",
         "keywords": [r"(not|never) (receiv\w*|get|getting|com\w*)", r"delay\w*", r"late"],
         "action": "Measure how many alerts arrive and how late; send pickup-critical alerts by SMS as a backup.",
         "owner": "Mobile app team", "effort": 2,
         "measure": "Alert delivery rate and delay",
         "check_first": "Push notification delivery reports"},
    ],
    "cab_delay": [
        {"id": "no_show", "name": "Marked \"no-show\" unfairly",
         "keywords": [r"no[- ]?show\w*", r"marked (me )?absent", r"didn'?t wait", r"don'?t (even )?wait"],
         "action": "Allow a no-show only after the driver has called the employee and the cab's GPS shows it was at "
                   "the pickup point.",
         "owner": "Operations (vendors) + product", "effort": 3,
         "measure": "No-shows without a call or GPS proof",
         "check_first": "Driver call logs and GPS at the time of each no-show"},
        {"id": "late", "name": "Cab late / never came",
         "keywords": [r"late", r"delay\w*", r"on time", r"never (came|come)", r"wait\w*"],
         "action": "Share weekly on-time numbers by vendor and route with the employer's transport desk, and act on "
                   "routes that are late again and again.",
         "owner": "Operations (transport desk + vendors)", "effort": 5,
         "measure": "On-time pickup rate by vendor and route",
         "check_first": "Scheduled vs actual pickup times by vendor"},
    ],
    "routing": [
        {"id": "pickup_point", "name": "Pickup points too far or removed",
         "keywords": [r"pick ?-?up (point|location)s?", r"nodal\w*", r"walk\w*", r"far", r"stops?", r"boarding points?"],
         "action": "Agree a maximum walking distance to pickup points with each employer, and review points that were "
                   "removed.",
         "owner": "Operations + customer success (employer settings)", "effort": 3,
         "measure": "Average walking distance to pickup points",
         "check_first": "Distance from employees' addresses to their assigned pickup point"},
        {"id": "long_route", "name": "Routes too long / too many pickups",
         "keywords": [r"rout(e|es|ing)", r"long", r"hours?", r"pooling", r"club\w*", r"sequence"],
         "action": "Set a maximum ride time per employee and review the routes that break it.",
         "owner": "Routing team + operations", "effort": 4,
         "measure": "Share of trips longer than the agreed maximum",
         "check_first": "Ride time per employee compared with direct travel time"},
    ],
    "support": [
        {"id": "contact_driver", "name": "Can't call or message the driver",
         "keywords": [r"(call|contact|connect|reach|chat)\w*.{0,20}driver", r"driver.{0,15}(number|contact)",
                      r"call(ing)? (option|permission)", r"calls? (are )?not connect\w*"],
         "action": "Make in-app calling to the driver reliable (with numbers hidden for privacy) or add in-app chat for "
                   "the trip. Check whether the employer has switched calling off.",
         "owner": "Mobile app team + calling provider", "effort": 2,
         "measure": "Share of in-app calls that connect",
         "check_first": "Call logs by provider and error; employer calling settings"},
        {"id": "no_feedback", "name": "No way to give feedback or report a problem",
         "keywords": [r"feedback\w*", r"rate (the )?driver", r"driver rating", r"report\w*"],
         "action": "Add a \"Report a problem\" button with ticket status, so complaints reach the right team instead of "
                   "the Play Store.",
         "owner": "Product + support team", "effort": 3,
         "measure": "Problems reported in the app; their share of Play Store complaints",
         "check_first": "Current feedback channels and how many tickets they get"},
        {"id": "helpdesk", "name": "Helpdesk doesn't respond",
         "keywords": [r"help ?desk", r"support", r"no response", r"complain\w*", r"escalat\w*"],
         "action": "Measure how fast the helpdesk replies and solves issues, and set a target everyone can see.",
         "owner": "Support team + operations", "effort": 3,
         "measure": "Time to first reply; time to resolve",
         "check_first": "Ticket data: volumes, reply times, unresolved tickets"},
    ],
    "usability": [
        {"id": "new_ui_worse", "name": "New design worse than the old one",
         "keywords": [r"(old|previous|earlier) (app|version|ui)", r"new (ui|design|update|version|app)", r"removed"],
         "action": "Test the new screens with 5–8 employees against the old ones, and bring back features people "
                   "miss (for example, seeing co-passengers).",
         "owner": "Product + design", "effort": 3,
         "measure": "Task success in user tests; design-related complaints",
         "check_first": "Which features were removed or moved in recent releases"},
        {"id": "dark_mode", "name": "No dark mode",
         "keywords": [r"dark (mode|theme)"],
         "action": "Follow the phone's dark mode setting (many people use the app early morning or late at night).",
         "owner": "Mobile app team + design", "effort": 2,
         "measure": "Dark-mode requests",
         "check_first": "Share of users with dark mode on"},
        {"id": "not_friendly", "name": "Hard to use / confusing",
         "keywords": [r"user ?-?friendly", r"confus\w*", r"difficult", r"complicated", r"too many (taps|clicks|steps)"],
         "action": "Watch 5 employees book and track a trip, and fix the three places where they get stuck.",
         "owner": "Product + design", "effort": 3,
         "measure": "Steps and time to book a trip",
         "check_first": "Screen analytics: where users drop off or go back"},
    ],
}
