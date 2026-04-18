IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='applicants' AND xtype='U')
BEGIN
    CREATE TABLE applicants (
        id INT IDENTITY(1,1) PRIMARY KEY,
        age INT NOT NULL,
        sex NVARCHAR(10) NOT NULL,
        bmi FLOAT NOT NULL,
        children INT NOT NULL,
        smoker NVARCHAR(10) NOT NULL,
        region NVARCHAR(50) NOT NULL,
        created_at NVARCHAR(32) NOT NULL,
        updated_at NVARCHAR(32) NOT NULL
    )
END

