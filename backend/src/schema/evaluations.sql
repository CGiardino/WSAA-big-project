IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='applicant_evaluations' AND xtype='U')
BEGIN
    CREATE TABLE applicant_evaluations (
        id INT IDENTITY(1,1) PRIMARY KEY,
        evaluation_id NVARCHAR(64) NOT NULL UNIQUE,
        applicant_id INT NOT NULL,
        risk_category NVARCHAR(20) NOT NULL,
        model_version NVARCHAR(32) NOT NULL,
        created_at NVARCHAR(32) NOT NULL,
        FOREIGN KEY(applicant_id) REFERENCES applicants(id)
    )
END

