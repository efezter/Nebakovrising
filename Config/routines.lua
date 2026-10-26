-- Durations in seconds; shift times in game hours (0-24).
-- Edit this file, then reload the save/restart the game.
return {
    version = 1,
    breakfast = { minSeconds = 20, maxSeconds = 50 },
    eveningMeal = { minSeconds = 50, maxSeconds = 120 },
    patrol = { minSeconds = 10, maxSeconds = 180 },
    wakeStagger = { minSeconds = 5, maxSeconds = 15 },
    eveningMealStagger = { minSeconds = 10, maxSeconds = 30 },
    shifts = {
        day = { wakeHour = 8, mealHour = 20, sleepHour = 0 },
        night = { wakeHour = 19, mealHour = 8, sleepHour = 11 },
    },
    subtitles = { enabled = true, maxDistance = 24, fontSize = 1.15, height = 2.1 },
    dice = { enabled = true, firstPairOnly = true, searchRadius = 120,
        pairWaitSeconds = 90, approachTimeout = 90, playSeconds = 120 },
}
