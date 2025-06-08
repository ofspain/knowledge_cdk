-- Database initialization script with transaction support and error handling

START TRANSACTION;

-- Create users table if not exists
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_username (username),
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Insert initial data only if tables are empty
INSERT IGNORE INTO users (username, email)
SELECT * FROM (
    SELECT 'admin' AS username, 'admin@example.com' AS email
    UNION SELECT 'user1', 'user1@example.com'
    UNION SELECT 'user2', 'user2@example.com'
) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM users);

-- Create stored procedure for user creation
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS create_user(
    IN p_username VARCHAR(100),
    IN p_email VARCHAR(255)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    INSERT INTO users (username, email)
    VALUES (p_username, p_email);

    INSERT INTO audit_log (user_id, action, description)
    VALUES (LAST_INSERT_ID(), 'USER_CREATE', CONCAT('Created user: ', p_username));

    COMMIT;
END //
DELIMITER ;

COMMIT;

-- Create database user with limited privileges
CREATE USER IF NOT EXISTS 'app_user'@'%' IDENTIFIED BY '${APP_USER_PASSWORD}';
GRANT SELECT, INSERT, UPDATE, DELETE ON ${DB_NAME}.* TO 'app_user'@'%';
FLUSH PRIVILEGES;