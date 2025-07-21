# MyNetDiary Grafana Queries

This file contains useful Flux queries for creating Grafana dashboards with your MyNetDiary data.

## Meal Summary Queries

### Daily Calorie Intake by Meal

```flux
from(bucket: "mynetdiary")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "meal_summary")
  |> filter(fn: (r) => r._field == "calories")
  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
  |> yield(name: "daily_calories")
```

### Macronutrient Breakdown

```flux
from(bucket: "mynetdiary")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "meal_summary")
  |> filter(fn: (r) => r._field == "protein" or r._field == "total_fat" or r._field == "total_carbs")
  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> yield(name: "macros")
```

### Calories by Meal Type

```flux
from(bucket: "mynetdiary")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "meal_summary")
  |> filter(fn: (r) => r._field == "calories")
  |> pivot(rowKey:["_time"], columnKey: ["meal"], valueColumn: "_value")
  |> yield(name: "meal_calories")
```

### Sodium Intake Over Time

```flux
from(bucket: "mynetdiary")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "meal_summary")
  |> filter(fn: (r) => r._field == "sodium")
  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
  |> yield(name: "sodium")
```

### Fiber Intake Over Time

```flux
from(bucket: "mynetdiary")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "meal_summary")
  |> filter(fn: (r) => r._field == "fiber")
  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
  |> yield(name: "fiber")
```

## Individual Food Queries

### Most Common Foods

```flux
from(bucket: "mynetdiary")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "nutrition_data")
  |> filter(fn: (r) => r._field == "Calories")
  |> group(columns: ["food_name"])
  |> count()
  |> sort(columns: ["_value"], desc: true)
  |> limit(n: 10)
  |> yield(name: "common_foods")
```

### Foods with Highest Protein/Calorie Ratio

```flux
from(bucket: "mynetdiary")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "nutrition_data")
  |> filter(fn: (r) => r._field == "Protein" or r._field == "Calories")
  |> pivot(rowKey:["_time", "food_name"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({ r with ratio: r.Protein / r.Calories }))
  |> filter(fn: (r) => r.Calories > 50)
  |> sort(columns: ["ratio"], desc: true)
  |> limit(n: 10)
  |> yield(name: "protein_efficiency")
```
