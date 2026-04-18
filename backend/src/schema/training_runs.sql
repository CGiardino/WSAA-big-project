IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='training_runs' AND xtype='U')
BEGIN
    CREATE TABLE training_runs (
        run_id NVARCHAR(64) PRIMARY KEY,
        status NVARCHAR(32) NOT NULL,
        epochs INT,
        model_version NVARCHAR(32),
        classification_report NVARCHAR(MAX),
        started_at NVARCHAR(32),
        finished_at NVARCHAR(32),
        last_error NVARCHAR(255)
    )
END

