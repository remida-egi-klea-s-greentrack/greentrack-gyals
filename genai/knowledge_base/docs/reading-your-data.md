# Reading GreenTrack data: sub-meters, forecast and anomalies

GreenTrack uses the UCI "Individual household electric power consumption" dataset: one house near Paris, measured every minute from December 2006 to November 2010 and aggregated to hours.

What the numbers mean:
- Total consumption (global active power) is the whole house in kWh per hour.
- sub_metering_1 (kitchen): dishwasher, oven and microwave.
- sub_metering_2 (laundry): washing machine, tumble dryer, refrigerator and a light.
- sub_metering_3: electric water heater and air conditioner.
- "Other" is total minus the three sub-meters: lighting, electronics and any other appliances.

How to use them for saving energy:
- Start with the largest share in the submetering breakdown and apply the advice for that area (water heating, laundry, kitchen, heating and cooling, standby power).
- The day-ahead forecast shows what is typical for the coming hours; consumption well above it points to an unusual appliance run.
- Anomaly scores are percentiles against past behaviour, not probabilities. log-MAD flags one hour that is unusual for its hour of the week; Random Cut Forest flags an unusually heavy day (24 hours as a whole).

Source: UCI Machine Learning Repository, "Individual household electric power consumption" dataset description.
