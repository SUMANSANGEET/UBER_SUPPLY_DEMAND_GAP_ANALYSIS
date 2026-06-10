-- ============================================================
--  UBER SUPPLY-DEMAND GAP ANALYSIS
--  SQL Insights File  |  SQLite Compatible
--  Dataset : Uber_Request_Data.csv  (6,745 rows)
--  Period  : 11 Jul 2016 – 15 Jul 2016  (5 weekdays)
--  Author  : Suman  |  Data Analyst Internship – Cohort 2025
-- ============================================================
--
--  HOW TO RUN
--  ----------
--  1. Load the cleaned dataset into a table named `uber`
--     with these columns:
--
--     RequestId   INTEGER   -- unique ride request ID
--     PickupPoint TEXT      -- 'Airport' or 'City'
--     DriverId    INTEGER   -- 0 when no car available
--     Status      TEXT      -- 'Trip Completed' | 'Cancelled' | 'No Cars Available'
--     Hour        INTEGER   -- 0–23 (from Request timestamp)
--     Date        TEXT      -- YYYY-MM-DD
--     DayOfWeek   TEXT      -- Monday … Friday
--     TimeSlot    TEXT      -- 'Early Morning'|'Morning'|'Afternoon'|
--                           --   'Evening'|'Late Night'|'Night'
--     Unfulfilled INTEGER   -- 1 = Cancelled or No Cars Available; 0 = Completed
--     DurMin      REAL      -- trip duration in minutes (NULL if not completed)
--
--  2. Execute this file top-to-bottom in any SQLite client
--     (DB Browser for SQLite, DBeaver, Python sqlite3, etc.)
--
-- ============================================================
--  TABLE OF CONTENTS
-- ============================================================
--
--  SECTION A  –  STATUS & FULFILMENT OVERVIEW
--    Q01  Overall Request Status Distribution
--    Q02  Fulfilment Rate Summary (single-row KPI)
--
--  SECTION B  –  TIME-OF-DAY ANALYSIS
--    Q03  Supply-Demand Gap by Time Slot
--    Q04  Top-10 Peak Gap Hours (ranked by unfulfilled count)
--    Q05  Hourly Cancellation Rate vs No-Cars Rate
--
--  SECTION C  –  PICKUP POINT ANALYSIS
--    Q06  Cancellation & No-Cars Rate by Pickup Point
--    Q07  Worst Pickup × Time-Slot Combinations (with severity label)
--    Q08  Failure-Mode Breakdown: Pickup × Time Slot Matrix
--
--  SECTION D  –  DAILY TREND ANALYSIS
--    Q09  Daily Request Trend (5-day view)
--    Q10  Day-over-Day Completion Rate Comparison
--
--  SECTION E  –  TRIP DURATION ANALYSIS
--    Q11  Trip Duration Statistics by Pickup Point
--    Q12  Average Trip Duration by Time Slot
--
--  SECTION F  –  DRIVER ANALYSIS
--    Q13  Top-10 Drivers by Completed Trips
--    Q14  Driver Workload Distribution (bucket histogram)
--
--  SECTION G  –  ADVANCED  (Window Functions & Subqueries)
--    Q15  Running Cumulative Gap % by Hour (Window Function)
--
-- ============================================================



-- ============================================================
--  SECTION A  –  STATUS & FULFILMENT OVERVIEW
-- ============================================================

-- -------------------------------------------------------
-- Q01  Overall Request Status Distribution
-- -------------------------------------------------------
-- PURPOSE : Establish the baseline split between Completed,
--           Cancelled, and No Cars Available requests.
-- KEY INSIGHT : Only 42% of all requests are completed.
--              No Cars Available (39.3%) is as large as
--              Completed — a fleet-shortage crisis.
-- -------------------------------------------------------

SELECT
    Status,
    COUNT(*)                                                    AS Total_Requests,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM uber), 2)   AS Pct_Share,
    CASE
        WHEN Status = 'Trip Completed'    THEN 'Fulfilled   ✅'
        WHEN Status = 'Cancelled'         THEN 'Unfulfilled ❌'
        ELSE                                   'Unfulfilled 🚫'
    END                                                         AS Fulfillment_Type
FROM uber
GROUP BY Status
ORDER BY Total_Requests DESC;

-- Expected output:
-- Status                | Total_Requests | Pct_Share | Fulfillment_Type
-- Trip Completed        |          2831  |     41.97 | Fulfilled   ✅
-- No Cars Available     |          2650  |     39.29 | Unfulfilled 🚫
-- Cancelled             |          1264  |     18.74 | Unfulfilled ❌


-- -------------------------------------------------------
-- Q02  Fulfilment Rate Summary  (single-row executive KPI)
-- -------------------------------------------------------
-- PURPOSE : One-line business scorecard for the entire dataset.
-- KEY INSIGHT : 58% gap rate, 300 active drivers,
--              avg trip 52.4 min, 5 days of data.
-- -------------------------------------------------------

SELECT
    COUNT(*)                                                              AS Total_Requests,
    SUM(CASE WHEN Status = 'Trip Completed'    THEN 1 ELSE 0 END)        AS Total_Completed,
    SUM(CASE WHEN Status = 'Cancelled'         THEN 1 ELSE 0 END)        AS Total_Cancelled,
    SUM(CASE WHEN Status = 'No Cars Available' THEN 1 ELSE 0 END)        AS Total_No_Cars,
    SUM(Unfulfilled)                                                      AS Total_Unfulfilled,
    ROUND(
        SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 2)                                              AS Completion_Rate_Pct,
    ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 2)                        AS Gap_Rate_Pct,
    COUNT(DISTINCT DriverId)                                              AS Active_Drivers,
    COUNT(DISTINCT Date)                                                  AS Days_Observed,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT Date), 0)                      AS Avg_Daily_Requests,
    ROUND(AVG(CASE WHEN DurMin IS NOT NULL THEN DurMin END), 2)          AS Avg_Trip_Duration_Min
FROM uber;



-- ============================================================
--  SECTION B  –  TIME-OF-DAY ANALYSIS
-- ============================================================

-- -------------------------------------------------------
-- Q03  Supply-Demand Gap by Time Slot
-- -------------------------------------------------------
-- PURPOSE : Rank each time slot by how many requests go
--           unfulfilled — both in raw count and as a rate.
-- KEY INSIGHT : Morning has the highest absolute gap (1,249)
--              driven by cancellations. Late Night has the
--              worst rate (66.7%) driven by no cars at Airport.
-- -------------------------------------------------------

SELECT
    TimeSlot,
    COUNT(*)                                                    AS Total_Requests,
    SUM(Unfulfilled)                                            AS Unfulfilled_Count,
    COUNT(*) - SUM(Unfulfilled)                                 AS Completed_Count,
    ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 1)              AS Gap_Pct,
    ROUND((COUNT(*) - SUM(Unfulfilled)) * 100.0 / COUNT(*), 1) AS Completion_Pct
FROM uber
GROUP BY TimeSlot
ORDER BY Unfulfilled_Count DESC;


-- -------------------------------------------------------
-- Q04  Top-10 Peak Gap Hours  (ranked by unfulfilled count)
-- -------------------------------------------------------
-- PURPOSE : Identify the exact clock-hours that accumulate
--           the most unfulfilled requests to guide shift design.
-- KEY INSIGHT : Hour 18 (6 PM) is the worst — 346 unfulfilled
--              out of 510 total (67.8% gap). Hours 17–21 form
--              a 5-hour evening dead zone at Airport.
-- -------------------------------------------------------

SELECT
    Hour,
    TimeSlot,
    COUNT(*)                                                        AS Total_Requests,
    SUM(Unfulfilled)                                                AS Unfulfilled,
    SUM(CASE WHEN Status = 'Cancelled'         THEN 1 ELSE 0 END)  AS Cancelled,
    SUM(CASE WHEN Status = 'No Cars Available' THEN 1 ELSE 0 END)  AS No_Cars,
    ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 1)                  AS Gap_Pct
FROM uber
GROUP BY Hour
ORDER BY Unfulfilled DESC
LIMIT 10;


-- -------------------------------------------------------
-- Q05  Hourly Cancellation Rate vs No-Cars Rate (all 24 h)
-- -------------------------------------------------------
-- PURPOSE : Show the full 24-hour profile of both failure
--           modes side-by-side to prove they are time-separated.
-- KEY INSIGHT : Cancel_Pct peaks at 5–9h (City Morning);
--              NoCar_Pct peaks at 17–21h (Airport Evening).
--              The two failure modes are ~12 hours apart —
--              requiring two completely different interventions.
-- -------------------------------------------------------

SELECT
    Hour,
    TimeSlot,
    COUNT(*)                                                              AS Total_Requests,
    SUM(CASE WHEN Status = 'Cancelled'         THEN 1 ELSE 0 END)        AS Cancelled,
    SUM(CASE WHEN Status = 'No Cars Available' THEN 1 ELSE 0 END)        AS No_Cars,
    SUM(CASE WHEN Status = 'Trip Completed'    THEN 1 ELSE 0 END)        AS Completed,
    ROUND(
        SUM(CASE WHEN Status = 'Cancelled' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                              AS Cancel_Pct,
    ROUND(
        SUM(CASE WHEN Status = 'No Cars Available' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                              AS NoCar_Pct,
    ROUND(
        SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                              AS Completion_Pct
FROM uber
GROUP BY Hour
ORDER BY Hour;



-- ============================================================
--  SECTION C  –  PICKUP POINT ANALYSIS
-- ============================================================

-- -------------------------------------------------------
-- Q06  Cancellation & No-Cars Rate by Pickup Point
-- -------------------------------------------------------
-- PURPOSE : Confirm that Airport and City have fundamentally
--           different failure modes.
-- KEY INSIGHT : Airport = No Cars problem (52.9% no-car rate).
--              City     = Cancellation problem (30.4% cancel rate).
--              One-size-fits-all solutions will fail both.
-- -------------------------------------------------------

SELECT
    PickupPoint,
    COUNT(*)                                                                AS Total_Requests,
    SUM(CASE WHEN Status = 'Trip Completed'    THEN 1 ELSE 0 END)          AS Completed,
    SUM(CASE WHEN Status = 'Cancelled'         THEN 1 ELSE 0 END)          AS Cancelled,
    SUM(CASE WHEN Status = 'No Cars Available' THEN 1 ELSE 0 END)          AS No_Cars,
    ROUND(
        SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 2)                                                AS Completion_Rate_Pct,
    ROUND(
        SUM(CASE WHEN Status = 'Cancelled' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 2)                                                AS Cancel_Rate_Pct,
    ROUND(
        SUM(CASE WHEN Status = 'No Cars Available' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 2)                                                AS NoCar_Rate_Pct
FROM uber
GROUP BY PickupPoint
ORDER BY PickupPoint;


-- -------------------------------------------------------
-- Q07  Worst Pickup × Time-Slot Combinations  (Top 10)
--       with CASE-based Severity Label
-- -------------------------------------------------------
-- PURPOSE : Rank every pickup × time-slot segment by unfulfilled
--           count and tag each with a severity level.
-- KEY INSIGHT : City Morning (1,205 unfulfilled, 71.9% gap) and
--              Airport Late Night (911 unfulfilled, 79.3% gap)
--              together account for 55% of ALL unfulfilled requests.
--              Fixing just these 2 segments eliminates the majority
--              of the supply-demand problem.
-- -------------------------------------------------------

SELECT
    PickupPoint,
    TimeSlot,
    COUNT(*)                                                    AS Total_Requests,
    SUM(Unfulfilled)                                            AS Unfulfilled,
    COUNT(*) - SUM(Unfulfilled)                                 AS Completed,
    ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 1)              AS Gap_Pct,
    CASE
        WHEN ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 1) >= 70
            THEN '🔴 CRITICAL  (≥70%)'
        WHEN ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 1) >= 50
            THEN '🟠 HIGH      (50–69%)'
        WHEN ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 1) >= 30
            THEN '🟡 MEDIUM    (30–49%)'
        ELSE
            '🟢 LOW       (<30%)'
    END                                                         AS Severity
FROM uber
GROUP BY PickupPoint, TimeSlot
ORDER BY Unfulfilled DESC
LIMIT 10;


-- -------------------------------------------------------
-- Q08  Failure-Mode Breakdown: Pickup × Time Slot Matrix
--       (Cancellation % vs No-Cars % for all 12 segments)
-- -------------------------------------------------------
-- PURPOSE : Show the root-cause split for every combination
--           of pickup point and time slot simultaneously.
-- KEY INSIGHT : Airport Late Night is 77% No Cars — pure fleet
--              shortage. City Morning is 66% Cancellations —
--              pure driver behaviour. Different fixes required.
-- -------------------------------------------------------

SELECT
    PickupPoint,
    TimeSlot,
    COUNT(*)                                                                  AS Total,
    SUM(CASE WHEN Status = 'Trip Completed'    THEN 1 ELSE 0 END)            AS Completed,
    SUM(CASE WHEN Status = 'Cancelled'         THEN 1 ELSE 0 END)            AS Cancelled,
    SUM(CASE WHEN Status = 'No Cars Available' THEN 1 ELSE 0 END)            AS No_Cars,
    ROUND(
        SUM(CASE WHEN Status = 'Cancelled' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                                  AS Cancel_Pct,
    ROUND(
        SUM(CASE WHEN Status = 'No Cars Available' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                                  AS NoCar_Pct,
    ROUND(
        SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                                  AS Completion_Pct,
    CASE
        WHEN SUM(CASE WHEN Status = 'Cancelled' THEN 1 ELSE 0 END)
           > SUM(CASE WHEN Status = 'No Cars Available' THEN 1 ELSE 0 END)
            THEN 'Cancellations Dominate'
        ELSE
            'No Cars Dominates'
    END                                                                       AS Primary_Failure_Mode
FROM uber
GROUP BY PickupPoint, TimeSlot
ORDER BY PickupPoint, TimeSlot;



-- ============================================================
--  SECTION D  –  DAILY TREND ANALYSIS
-- ============================================================

-- -------------------------------------------------------
-- Q09  Daily Request Trend  (5-day view)
-- -------------------------------------------------------
-- PURPOSE : Show whether the gap is a one-day spike or a
--           persistent structural problem.
-- KEY INSIGHT : Daily totals range only 1,307–1,381 across
--              all 5 days. The gap is flat every day —
--              confirming a structural, not episodic, problem.
--              Thursday has the worst completion rate (39.2%).
-- -------------------------------------------------------

SELECT
    Date,
    DayOfWeek,
    COUNT(*)                                                              AS Total_Requests,
    SUM(CASE WHEN Status = 'Trip Completed'    THEN 1 ELSE 0 END)        AS Completed,
    SUM(CASE WHEN Status = 'Cancelled'         THEN 1 ELSE 0 END)        AS Cancelled,
    SUM(CASE WHEN Status = 'No Cars Available' THEN 1 ELSE 0 END)        AS No_Cars,
    SUM(Unfulfilled)                                                      AS Total_Unfulfilled,
    ROUND(
        SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                              AS Completion_Pct,
    ROUND(SUM(Unfulfilled) * 100.0 / COUNT(*), 1)                        AS Gap_Pct
FROM uber
GROUP BY Date, DayOfWeek
ORDER BY Date;


-- -------------------------------------------------------
-- Q10  Day-over-Day Completion Rate Comparison
--       (with deviation from weekly average)
-- -------------------------------------------------------
-- PURPOSE : Identify the best and worst days and quantify
--           how far each day deviates from the 5-day average.
-- KEY INSIGHT : All 5 days are within ±3% of the mean —
--              no single day is an outlier. The problem is
--              uniform across the entire working week.
-- -------------------------------------------------------

SELECT
    Date,
    DayOfWeek,
    ROUND(
        SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)                                              AS Completion_Pct,
    ROUND(
        SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
        / COUNT(*) * 100, 1)
        - (SELECT ROUND(
                SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
                / COUNT(*) * 100, 1)
             FROM uber)                                                   AS Deviation_From_Avg,
    CASE
        WHEN ROUND(
                SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
                / COUNT(*) * 100, 1)
           = (SELECT MAX(daily_comp)
              FROM (SELECT Date,
                           ROUND(SUM(CASE WHEN Status='Trip Completed' THEN 1.0 ELSE 0 END)
                                 / COUNT(*) * 100, 1) AS daily_comp
                    FROM uber GROUP BY Date))
            THEN '🏆 Best Day'
        WHEN ROUND(
                SUM(CASE WHEN Status = 'Trip Completed' THEN 1.0 ELSE 0 END)
                / COUNT(*) * 100, 1)
           = (SELECT MIN(daily_comp)
              FROM (SELECT Date,
                           ROUND(SUM(CASE WHEN Status='Trip Completed' THEN 1.0 ELSE 0 END)
                                 / COUNT(*) * 100, 1) AS daily_comp
                    FROM uber GROUP BY Date))
            THEN '⚠️  Worst Day'
        ELSE '—'
    END                                                                   AS Rank_Label
FROM uber
GROUP BY Date, DayOfWeek
ORDER BY Date;



-- ============================================================
--  SECTION E  –  TRIP DURATION ANALYSIS
-- ============================================================

-- -------------------------------------------------------
-- Q11  Trip Duration Statistics by Pickup Point
-- -------------------------------------------------------
-- PURPOSE : Check whether route distance explains the gap —
--           e.g. do drivers cancel because Airport runs are longer?
-- KEY INSIGHT : Airport avg = 52.2 min, City avg = 52.6 min.
--              Durations are virtually identical — duration is
--              NOT the reason drivers cancel. The cause is
--              scheduling and incentive structure.
-- -------------------------------------------------------

SELECT
    PickupPoint,
    COUNT(*)                                    AS Completed_Trips,
    ROUND(AVG(DurMin),  2)                      AS Avg_Duration_Min,
    ROUND(MIN(DurMin),  2)                      AS Min_Duration_Min,
    ROUND(MAX(DurMin),  2)                      AS Max_Duration_Min,
    ROUND(MAX(DurMin) - MIN(DurMin), 2)         AS Full_Range_Min,
    -- Approximate standard deviation via variance formula
    ROUND(
        SQRT(
            AVG(DurMin * DurMin) - AVG(DurMin) * AVG(DurMin)
        ), 2)                                   AS Approx_StdDev_Min
FROM uber
WHERE Status  = 'Trip Completed'
  AND DurMin IS NOT NULL
GROUP BY PickupPoint
ORDER BY PickupPoint;


-- -------------------------------------------------------
-- Q12  Average Trip Duration by Time Slot
-- -------------------------------------------------------
-- PURPOSE : Understand how traffic conditions across the day
--           affect trip length for completed rides.
-- KEY INSIGHT : Late Night (55.2 min) and Evening (54.8 min)
--              have the longest trips — heavy airport traffic.
--              Morning (49.2 min) is the fastest — early starts
--              before congestion builds.
-- -------------------------------------------------------

SELECT
    TimeSlot,
    COUNT(*)                         AS Completed_Trips,
    ROUND(AVG(DurMin), 2)            AS Avg_Duration_Min,
    ROUND(MIN(DurMin), 2)            AS Min_Duration_Min,
    ROUND(MAX(DurMin), 2)            AS Max_Duration_Min
FROM uber
WHERE Status  = 'Trip Completed'
  AND DurMin IS NOT NULL
GROUP BY TimeSlot
ORDER BY Avg_Duration_Min DESC;



-- ============================================================
--  SECTION F  –  DRIVER ANALYSIS
-- ============================================================

-- -------------------------------------------------------
-- Q13  Top-10 Drivers by Completed Trips
-- -------------------------------------------------------
-- PURPOSE : Identify high-performing drivers and understand
--           whether workload is concentrated in a few drivers.
-- KEY INSIGHT : Top 10 drivers each completed 10–14 trips in
--              5 days (2–3 trips/day). Heavy concentration in
--              a small pool — fleet expansion is needed to
--              prevent driver burnout and coverage gaps.
-- -------------------------------------------------------

SELECT
    DriverId,
    COUNT(*)                              AS Trips_Completed,
    ROUND(AVG(DurMin), 2)                 AS Avg_Trip_Min,
    ROUND(MIN(DurMin), 2)                 AS Min_Trip_Min,
    ROUND(MAX(DurMin), 2)                 AS Max_Trip_Min,
    COUNT(DISTINCT PickupPoint)           AS Pickup_Points_Served,
    COUNT(DISTINCT Date)                  AS Days_Active
FROM uber
WHERE Status  = 'Trip Completed'
  AND DriverId > 0
  AND DurMin  IS NOT NULL
GROUP BY DriverId
ORDER BY Trips_Completed DESC
LIMIT 10;


-- -------------------------------------------------------
-- Q14  Driver Workload Distribution  (bucket histogram)
-- -------------------------------------------------------
-- PURPOSE : Reveal how trips are distributed across all drivers
--           to spot over-reliance on a small core group.
-- KEY INSIGHT : Most drivers completed 1–5 trips in 5 days —
--              very low utilisation. Meanwhile the top tier
--              (10+ trips) carries a disproportionate load.
--              Levelling utilisation could close part of the gap.
-- -------------------------------------------------------

SELECT
    CASE
        WHEN trip_count = 1          THEN '1 trip'
        WHEN trip_count BETWEEN 2 AND 4  THEN '2–4 trips'
        WHEN trip_count BETWEEN 5 AND 7  THEN '5–7 trips'
        WHEN trip_count BETWEEN 8 AND 9  THEN '8–9 trips'
        ELSE                              '10+ trips'
    END                          AS Workload_Bucket,
    COUNT(*)                     AS Num_Drivers,
    ROUND(COUNT(*) * 100.0
          / SUM(COUNT(*)) OVER(), 1) AS Driver_Pct
FROM (
    SELECT
        DriverId,
        COUNT(*) AS trip_count
    FROM uber
    WHERE Status  = 'Trip Completed'
      AND DriverId > 0
    GROUP BY DriverId
) AS driver_summary
GROUP BY Workload_Bucket
ORDER BY MIN(trip_count);



-- ============================================================
--  SECTION G  –  ADVANCED  (Window Functions & Subqueries)
-- ============================================================

-- -------------------------------------------------------
-- Q15  Running Cumulative Gap % by Hour  (Window Function)
-- -------------------------------------------------------
-- PURPOSE : Show how the total unfulfilled gap accumulates
--           hour-by-hour throughout the day, enabling precise
--           trigger-point identification for real-time alerts.
--
-- WINDOW FUNCTION USED :
--   SUM(...) OVER (ORDER BY Hour
--                 ROWS BETWEEN UNBOUNDED PRECEDING
--                 AND CURRENT ROW)
--   → Computes a running total partitioned by nothing
--     (across the whole result set), ordered by hour.
--
-- KEY INSIGHTS :
--   • By hour  8 (8 AM)  → ~27% of the day's gap is done
--     (City Morning cancellations already accumulating)
--   • By hour 18 (6 PM)  → ~65% of the day's gap is done
--     (Airport evening no-cars explosion)
--   • By hour 21 (9 PM)  → >90% of the day's gap is done
--   → Fixing hours 5–9 and 17–21 would eliminate ~80%
--     of all unfulfilled requests for the day.
-- -------------------------------------------------------

SELECT
    Hour,
    TimeSlot,

    -- Hourly unfulfilled count
    SUM(Unfulfilled)                                                    AS Hourly_Gap,

    -- Running total of unfulfilled (cumulative sum, window function)
    SUM(SUM(Unfulfilled))
        OVER (
            ORDER BY Hour
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                                               AS Running_Total_Gap,

    -- Cumulative gap as % of full-day total
    ROUND(
        SUM(SUM(Unfulfilled))
            OVER (
                ORDER BY Hour
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
        * 100.0
        / SUM(SUM(Unfulfilled)) OVER (),
        1
    )                                                                   AS Cumulative_Gap_Pct,

    -- Hourly gap as % of this hour's total requests
    ROUND(
        SUM(Unfulfilled) * 100.0 / COUNT(*),
        1
    )                                                                   AS Hourly_Gap_Rate_Pct,

    -- Hourly completed count (supply)
    SUM(CASE WHEN Status = 'Trip Completed' THEN 1 ELSE 0 END)         AS Hourly_Completed

FROM uber
GROUP BY Hour, TimeSlot
ORDER BY Hour;


-- ============================================================
--  END OF FILE
-- ============================================================
--
--  SUMMARY OF KEY FINDINGS
--  ─────────────────────────────────────────────────────────
--  1. 58% of 6,745 requests are unfulfilled (Q01, Q02)
--  2. Airport = No Cars Available problem (Q06)
--  3. City    = Driver Cancellation problem (Q06)
--  4. Worst segment: Airport Late Night — 79.3% gap (Q07)
--  5. Second worst : City Morning — 71.9% gap (Q07)
--  6. These 2 segments alone = 55% of all unfulfilled (Q07)
--  7. Failure modes are 12h apart: Cancel@5–9h; NoCar@17–21h (Q05, Q15)
--  8. By 9 PM, >90% of the day's gap has already accumulated (Q15)
--  9. Gap is uniform across all 5 weekdays — structural (Q09, Q10)
-- 10. Trip duration is equal Airport ≈ City ≈ 52 min (Q11)
--     → Duration is NOT a cancellation driver
--
--  RECOMMENDED ACTIONS (from SQL evidence)
--  ─────────────────────────────────────────────────────────
--  • Priority 1 : Night driver shift at Airport (18–21h) [Q07, Q15]
--  • Priority 2 : Morning cancellation incentive, City (5–9h) [Q05, Q08]
--  • Priority 3 : Pre-scheduled Airport rides [Q04]
--  • Priority 4 : Fleet redistribution City→Airport at 16:00 [Q10, Q15]
--  • Priority 5 : Driver accountability programme [Q13, Q14]
--
-- ============================================================
