# Business Card Service

FastAPI backend for the Business Card frontend. Stores contacts in Azure SQL Database.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/contact` | Returns most recent contact |
| POST | `/api/contact` | Saves a new contact |
| POST | `/api/seed` | Seeds 20 random contacts |
| GET | `/api/health` | Health check |

## Environment Variables

```
DB_SERVER=your-server.database.windows.net
DB_NAME=your-database
DB_USER=your-username
DB_PASSWORD=your-password
DB_PORT=1433  # optional, default 1433
```

## Run Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Docker

### Build

```bash
docker build -t business-card-api .
```

### Run locally

```bash
docker run -p 8000:8000 \
  -e DB_SERVER=your-server.database.windows.net \
  -e DB_NAME=your-database \
  -e DB_USER=your-username \
  -e DB_PASSWORD=your-password \
  business-card-api
```

## Push to AWS ECR

### 1. Install and configure AWS CLI

```bash
aws configure
# Enter your AWS Access Key, Secret Key, region (e.g. us-east-1)
```

### 2. Create ECR repository (if not exists)

```bash
aws ecr create-repository --repository-name business-card-api --region us-east-1
```

### 3. Authenticate Docker to ECR

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

Replace `<account-id>` with your AWS account ID (e.g. `123456789012`).

### 4. Build and tag

```bash
# Get your ECR registry URI from AWS Console or:
aws ecr describe-repositories --repository-names business-card-api --query 'repositories[0].repositoryUri' --output text

# Build and tag (replace <account-id> and <region>)
docker build -t business-card-api .
docker tag business-card-api:latest <account-id>.dkr.ecr.<region>.amazonaws.com/business-card-api:latest
```

### 5. Push to ECR

```bash
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/business-card-api:latest
```

### One-liner (after AWS CLI is configured)

```bash
ECR_URI=$(aws ecr describe-repositories --repository-names business-card-api --query 'repositories[0].repositoryUri' --output text 2>/dev/null || aws ecr create-repository --repository-name business-card-api --query 'repository.repositoryUri' --output text)
docker build -t business-card-api .
docker tag business-card-api:latest $ECR_URI:latest
aws ecr get-login-password | docker login --username AWS --password-stdin ${ECR_URI%/*}
docker push $ECR_URI:latest
```
