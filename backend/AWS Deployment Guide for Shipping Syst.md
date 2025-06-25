# AWS Deployment Guide for Shipping System
## Complete Step-by-Step Guide

---

## Table of Contents
1. [AWS Suitability Assessment](#1-aws-suitability-assessment)
2. [Database Migration Strategy](#2-database-migration-strategy)
3. [Code Preparation & Changes](#3-code-preparation--changes)
4. [Cache Problem Solutions](#4-cache-problem-solutions)
5. [Domain Name Setup](#5-domain-name-setup)
6. [Step-by-Step AWS Deployment](#6-step-by-step-aws-deployment)
7. [Post-Deployment Checklist](#7-post-deployment-checklist)
8. [Cost Analysis](#8-cost-analysis)
9. [Recommended Architecture](#9-recommended-architecture)

---

## 1. AWS Suitability Assessment

### ✅ Why AWS is Perfect for Your Shipping System

**Free Tier Benefits:**
- **12 months free** for new accounts
- **Always free** services: Lambda, DynamoDB (limited), CloudWatch
- **EC2**: 750 hours/month of t2.micro instances
- **RDS**: 750 hours/month of db.t2.micro (PostgreSQL)
- **S3**: 5GB storage
- **Route 53**: DNS service (not free, but cheap)

**Advantages:**
- **Scalable**: Can grow with your business
- **Reliable**: 99.9% uptime SLA
- **Cost-effective**: Pay only for what you use
- **Security**: Built-in security features
- **Global**: Multiple regions available

---

## 2. Database Migration Strategy

### Option A: AWS RDS (Recommended)

**Step 1: Export Local Database**
```bash
# Export your current PostgreSQL database
pg_dump -U postgres -h localhost -d shipping_db > shipping_backup.sql
```

**Step 2: Create RDS Instance**
1. Go to AWS Console → RDS → Create Database
2. Choose PostgreSQL
3. Select Free tier template
4. Configure:
   - DB instance identifier: `shipping-db`
   - Master username: `postgres`
   - Master password: `your-secure-password`
   - Instance type: `db.t2.micro`
   - Storage: 20GB
   - Multi-AZ: No (free tier)

**Step 3: Import Data**
```bash
# Connect to your RDS instance
psql -U postgres -h your-rds-endpoint -d shipping_db < shipping_backup.sql
```

### Option B: EC2 with PostgreSQL
- Install PostgreSQL on EC2 instance
- More control but requires more management
- Good for development/testing

---

## 3. Code Preparation & Changes

### A. Environment Variables (.env file)
```bash
# Database Configuration
DB_NAME=shipping_db
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=your-rds-endpoint.amazonaws.com
DB_PORT=5432

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production-2024

# Email Configuration (Brevo)
SMTP_SERVER=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your_brevo_api_key
SMTP_PASSWORD=your_brevo_smtp_key
FROM_EMAIL=your_verified_sender_email@domain.com

# Encryption Key
ENCRYPTION_KEY=your_persistent_encryption_key

# Server Configuration
FLASK_ENV=production
FLASK_DEBUG=False
```

### B. Frontend Code Changes

**Current Code (Localhost):**
```javascript
fetch('http://localhost:5000/api/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
});
```

**Updated Code (Production):**
```javascript
const API_BASE_URL = 'https://your-domain.com';

fetch(`${API_BASE_URL}/api/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
});
```

**Files to Update:**
- `frontend/src/pages/Login.js`
- `frontend/src/pages/Register.js`
- `frontend/src/pages/UploadForm.js`
- `frontend/src/pages/Review.js`
- `frontend/src/pages/EditBill.js`
- `frontend/src/pages/UserApproval.js`
- `frontend/src/pages/BillSearch.js`
- `frontend/src/pages/EditDeleteBills.js`
- `frontend/src/pages/AccountPage.js`
- `frontend/src/pages/Contact.js`

### C. Backend CORS Configuration
```python
# In app.py
from flask_cors import CORS

# Update CORS configuration
CORS(app, origins=[
    'https://your-domain.com',
    'http://your-domain.com',
    'https://www.your-domain.com'
])
```

### D. Create Production Build Files

**Backend (requirements.txt):**
```bash
cd backend
pip freeze > requirements.txt
```

**Backend (Procfile):**
```bash
echo "web: gunicorn app:app" > Procfile
```

**Frontend (package.json update):**
```json
{
  "scripts": {
    "build": "react-scripts build",
    "start": "serve -s build -l 3000"
  },
  "dependencies": {
    "serve": "^14.0.0"
  }
}
```

---

## 4. Cache Problem Solutions

### Problem Analysis
Your cache issues are caused by:
1. **Browser Cache**: Old JavaScript/CSS files
2. **Service Workers**: Cached API responses
3. **Local Storage**: Stored tokens/data
4. **React Development Server**: Hot reloading issues

### Solutions

#### A. Backend Cache Headers
```python
# Add to your Flask app
@app.after_request
def add_cache_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
```

#### B. Frontend Cache Busting
```javascript
// Create config file: frontend/src/config.js
const config = {
  API_BASE_URL: process.env.NODE_ENV === 'production' 
    ? 'https://your-domain.com' 
    : 'http://localhost:5000',
  API_VERSION: 'v1'
};

export default config;
```

#### C. Service Worker Management
```javascript
// Add to your React app
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(function(registrations) {
        for(let registration of registrations) {
            registration.unregister();
        }
    });
}
```

#### D. Local Storage Management
```javascript
// Clear old data on app start
const clearOldData = () => {
  const lastVersion = localStorage.getItem('app_version');
  const currentVersion = '1.0.0';
  
  if (lastVersion !== currentVersion) {
    localStorage.clear();
    localStorage.setItem('app_version', currentVersion);
  }
};
```

---

## 5. Domain Name Setup

### AWS Route 53 Options
- **Domain Registration**: ~$12/year
- **Hosted Zones**: Free (50 zones)
- **Queries**: 1 million/month free

### Alternative Free Options
1. **Freenom**: Free domains (.tk, .ml, .ga, .cf)
2. **GitHub Pages**: Free hosting with custom domain
3. **Netlify**: Free hosting with custom domain

### Domain Setup Process
1. **Register Domain** (Route 53 or external)
2. **Create Hosted Zone** (if using Route 53)
3. **Add DNS Records**:
   - A Record: `@` → Your EC2/EB IP
   - CNAME: `www` → Your domain
4. **Request SSL Certificate** (AWS Certificate Manager)

---

## 6. Step-by-Step AWS Deployment

### Step 1: AWS Account Setup
1. **Create AWS Account**
   - Go to aws.amazon.com
   - Sign up for free tier
   - Add credit card (required)
   - Set up billing alerts

2. **Install AWS CLI**
   ```bash
   # Windows
   aws --version
   
   # Configure AWS CLI
   aws configure
   ```

### Step 2: Create RDS Database
1. **AWS Console** → RDS → Create Database
2. **Choose PostgreSQL**
3. **Template**: Free tier
4. **Settings**:
   - DB instance identifier: `shipping-db`
   - Master username: `postgres`
   - Master password: `your-secure-password`
5. **Instance configuration**:
   - Instance type: `db.t2.micro`
   - Storage: 20GB
   - Multi-AZ: No
6. **Connectivity**:
   - VPC: Default VPC
   - Public access: Yes
   - Security group: Create new
7. **Click Create Database**

### Step 3: Create S3 Bucket
1. **AWS Console** → S3 → Create Bucket
2. **Bucket name**: `your-shipping-app`
3. **Region**: Same as RDS
4. **Block all public access**: Yes
5. **Click Create Bucket**

### Step 4: Deploy Backend (Elastic Beanstalk)

#### A. Install EB CLI
```bash
pip install awsebcli
```

#### B. Initialize EB Application
```bash
cd backend
eb init -p python-3.9 your-shipping-app
```

#### C. Create Environment
```bash
eb create production
```

#### D. Configure Environment Variables
```bash
eb setenv DB_NAME=shipping_db
eb setenv DB_USER=postgres
eb setenv DB_PASSWORD=your_password
eb setenv DB_HOST=your-rds-endpoint
eb setenv JWT_SECRET_KEY=your_secret_key
eb setenv ENCRYPTION_KEY=your_encryption_key
```

#### E. Deploy
```bash
eb deploy
```

### Step 5: Deploy Frontend (S3 + CloudFront)

#### A. Build Frontend
```bash
cd frontend
npm install
npm run build
```

#### B. Upload to S3
```bash
aws s3 sync build/ s3://your-shipping-app
```

#### C. Create CloudFront Distribution
1. **AWS Console** → CloudFront → Create Distribution
2. **Origin Domain**: Your S3 bucket
3. **Viewer Protocol Policy**: Redirect HTTP to HTTPS
4. **Default Root Object**: index.html
5. **Error Pages**: Create custom error page for 403/404
6. **Click Create Distribution**

### Step 6: Configure Domain & SSL

#### A. Request SSL Certificate
1. **AWS Console** → Certificate Manager
2. **Request Certificate**
3. **Domain**: your-domain.com
4. **Validation**: DNS validation
5. **Add CNAME record** to your DNS

#### B. Update CloudFront
1. **Edit Distribution**
2. **SSL Certificate**: Custom certificate
3. **Select your certificate**
4. **Update Distribution**

---

## 7. Post-Deployment Checklist

### Security Checklist
- [ ] Update JWT_SECRET_KEY
- [ ] Set up AWS IAM roles
- [ ] Configure security groups
- [ ] Enable HTTPS everywhere
- [ ] Set up CloudWatch monitoring
- [ ] Enable RDS encryption
- [ ] Configure S3 bucket policies

### Performance Checklist
- [ ] Enable CloudFront caching
- [ ] Set up database connection pooling
- [ ] Configure auto-scaling groups
- [ ] Set up CloudWatch alarms
- [ ] Enable RDS performance insights
- [ ] Configure S3 lifecycle policies

### Backup & Recovery
- [ ] Enable RDS automated backups
- [ ] Set up S3 versioning
- [ ] Create disaster recovery plan
- [ ] Test backup restoration
- [ ] Document recovery procedures

### Monitoring & Logging
- [ ] Set up CloudWatch logs
- [ ] Configure error tracking
- [ ] Set up performance monitoring
- [ ] Create alert notifications
- [ ] Monitor costs

---

## 8. Cost Analysis

### Free Tier (First 12 Months)
| Service | Free Tier | Monthly Cost |
|---------|-----------|--------------|
| EC2 (t2.micro) | 750 hours | $0 |
| RDS (db.t2.micro) | 750 hours | $0 |
| S3 | 5GB | $0 |
| CloudFront | 1TB | $0 |
| Route 53 (domain) | N/A | $1 |
| **Total** | | **$1/month** |

### After Free Tier
| Service | Monthly Cost |
|---------|--------------|
| EC2 (t2.micro) | $8.47 |
| RDS (db.t2.micro) | $12.41 |
| S3 (10GB) | $0.23 |
| CloudFront (100GB) | $8.50 |
| Route 53 | $0.50 |
| **Total** | **$30.11/month** |

### Cost Optimization Tips
1. **Use Spot Instances** for non-critical workloads
2. **Enable RDS stop/start** for development
3. **Use S3 lifecycle policies** to move old data to cheaper storage
4. **Monitor with CloudWatch** to identify unused resources
5. **Use AWS Cost Explorer** to track spending

---

## 9. Recommended Architecture

```
Internet
    ↓
CloudFront (CDN)
    ↓
S3 (Static Files - Frontend)
    ↓
Application Load Balancer
    ↓
EC2/EBS (Backend API)
    ↓
RDS (PostgreSQL Database)
```

### Architecture Benefits
- **Scalability**: Auto-scaling groups
- **Reliability**: Multi-AZ deployment
- **Performance**: CDN for static files
- **Security**: HTTPS everywhere
- **Cost**: Pay-as-you-go model

### Security Layers
1. **CloudFront**: DDoS protection
2. **ALB**: SSL termination
3. **Security Groups**: Network access control
4. **IAM**: User access management
5. **RDS**: Database encryption

### Monitoring Stack
1. **CloudWatch**: Metrics and logs
2. **CloudTrail**: API logging
3. **X-Ray**: Distributed tracing
4. **SNS**: Alert notifications

---

## Additional Resources

### AWS Documentation
- [AWS Free Tier](https://aws.amazon.com/free/)
- [RDS User Guide](https://docs.aws.amazon.com/rds/)
- [EC2 User Guide](https://docs.aws.amazon.com/ec2/)
- [S3 User Guide](https://docs.aws.amazon.com/s3/)

### Tools & Services
- **AWS CLI**: Command line interface
- **AWS Console**: Web-based management
- **CloudFormation**: Infrastructure as code
- **CodeDeploy**: Automated deployments

### Support Options
- **AWS Support**: Paid support plans
- **AWS Community**: Free community support
- **Documentation**: Comprehensive guides
- **Training**: AWS training resources

---

## Conclusion

AWS provides an excellent platform for deploying your shipping system. The free tier allows you to get started without significant costs, and the scalable architecture ensures your system can grow with your business.

**Key Success Factors:**
1. **Plan thoroughly** before deployment
2. **Test everything** in a staging environment
3. **Monitor costs** and performance
4. **Keep security** as a top priority
5. **Document everything** for future maintenance

**Next Steps:**
1. Set up AWS account
2. Create RDS database
3. Prepare your code for production
4. Deploy backend to Elastic Beanstalk
5. Deploy frontend to S3/CloudFront
6. Configure domain and SSL
7. Test thoroughly
8. Monitor and optimize

Good luck with your deployment!