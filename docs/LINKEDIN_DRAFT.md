# LinkedIn draft — review before posting

I've been working on PRAVAHA AI, a traffic-simulation prototype that brings together full-stack development and machine learning.

It models three connected junctions in Pune using SUMO. A React dashboard shows simulated vehicle movement and signal states, while an XGBoost model forecasts the queue estimate 60 seconds ahead.

The backend uses FastAPI and WebSockets. I've also been improving the parts that make a demo trustworthy: clear connection status, measured analytics, signal-plan checks, and rollback to previous timings.

One important distinction: this is a simulation prototype, not a system deployed on real roads. The model's forecasting result is not proof of reduced traffic.

This project has helped me connect frontend work with Python, APIs, time-series features, and testing. I'd appreciate feedback on the dashboard, model evaluation, and what would make the prototype more useful.

Demo: [add the public URL once deployed]
Code: https://github.com/vedantjadhao17/PARVAHA_AI

#FullStackDevelopment #MachineLearning #React #Python #SUMO

---

Before posting:

- Replace the demo placeholder with a verified public URL, not localhost.
- Add a short screen recording showing the simulation, junction details, and forecast.
- Review the wording so it accurately reflects your own contribution and understanding.
- Describe the project as a simulation prototype; do not claim physical deployment, city-scale impact, or proven travel-time savings.
