# PROJECT PLAN

For the Web Services and Applications Big Project, I would like to extend my previous proof of concept, "Health Insurance Risk Classifier", developed for the Programming for Data Analytics course.
The original project focused on data analysis and a neural network model for classifying individuals into insurance risk categories. For this module, I plan to evolve it into a full web-based application with APIs, data persistence, and cloud deployment.

## Proposed Implementation Plan

### Week 1 - API & System Design
- Define REST API endpoints for submitting individual data and retrieving risk classifications.
- Design overall system architecture (API, data layer, ML integration).

### Week 2 - Backend Development
- Implement controllers, services, and data access layer.
- Integrate the trained ML model into the application.

### Week 3 - Data Persistence
- Implement database integration for storing and retrieving user and prediction data.
- Use Azure SQL locally via Docker to align local development with cloud deployment.

### Week 4 - External Data Integration
- Integrate with an external dataset or API to process sample individuals in batch.

### Week 5 - User Interface
- Develop a UI to interact with the system and visualize results.

### Week 6 - Cloud Deployment (Azure)
- Deploy application and database to Azure.
- Promote from local Dockerized Azure SQL setup to Azure SQL managed service.
- Configure auth access.

### Week 7 - Final Review & Submission
- Refine implementation and documentation.
- Final commit and submission.

