# 意图与槽位
先区分 query 与 plan。plan 场景仅为 date、banquet、gift、family_day、business。无法确定的字段返回 null，不猜测。

date: time, people, budget_per_person, cuisine, want_movie
banquet: time, people, total_budget, cuisine, private_room
gift: recipient, budget, preferences, occasion
family_day: child_age, duration, budget, interests, meal_preference
business: time, people, total_budget, level, quiet, meal_preference
