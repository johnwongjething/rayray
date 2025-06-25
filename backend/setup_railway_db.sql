-- Setup Railway Database for Shipping System

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'customer',
    approved BOOLEAN DEFAULT FALSE,
    customer_name VARCHAR(255),
    customer_email TEXT,
    customer_phone TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Bill of Lading table
CREATE TABLE IF NOT EXISTS bill_of_lading (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    customer_email TEXT,
    customer_phone TEXT,
    pdf_filename VARCHAR(255),
    ocr_text TEXT,
    shipper TEXT,
    consignee TEXT,
    port_of_loading VARCHAR(255),
    port_of_discharge VARCHAR(255),
    bl_number VARCHAR(255),
    container_numbers TEXT,
    service_fee DECIMAL(10,2),
    ctn_fee DECIMAL(10,2),
    payment_link TEXT,
    receipt_filename VARCHAR(255),
    status VARCHAR(100) DEFAULT 'Pending',
    invoice_filename VARCHAR(255),
    unique_number VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    receipt_uploaded_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    customer_username VARCHAR(255),
    customer_invoice VARCHAR(255),
    customer_packing_list VARCHAR(255)
);

-- Password Reset Tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Audit Logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    operation VARCHAR(255) NOT NULL,
    details TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_bill_of_lading_customer_name ON bill_of_lading(customer_name);
CREATE INDEX IF NOT EXISTS idx_bill_of_lading_status ON bill_of_lading(status);
CREATE INDEX IF NOT EXISTS idx_bill_of_lading_created_at ON bill_of_lading(created_at);
CREATE INDEX IF NOT EXISTS idx_bill_of_lading_bl_number ON bill_of_lading(bl_number);
CREATE INDEX IF NOT EXISTS idx_bill_of_lading_unique_number ON bill_of_lading(unique_number);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);

-- Insert default admin user (password: admin123)
INSERT INTO users (username, password_hash, role, approved, customer_name) 
VALUES ('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/HS.iQeO', 'admin', TRUE, 'System Administrator')
ON CONFLICT (username) DO NOTHING;

-- Insert a test staff user (password: staff123)
INSERT INTO users (username, password_hash, role, approved, customer_name) 
VALUES ('staff', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4J/HS.iQeO', 'staff', TRUE, 'Test Staff User')
ON CONFLICT (username) DO NOTHING; 