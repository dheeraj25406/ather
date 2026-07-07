#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Aether AWS EKS Deployment Script${NC}"

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v eksctl &> /dev/null; then
    echo -e "${RED}eksctl not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl not found. Please install it first.${NC}"
    exit 1
fi

# Configuration
CLUSTER_NAME=${CLUSTER_NAME:-"aether-prod"}
REGION=${REGION:-"us-east-1"}
ECR_REPO=${ECR_REPO:-"aether"}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo -e "${GREEN}Configuration:${NC}"
echo "  Cluster Name: $CLUSTER_NAME"
echo "  Region: $REGION"
echo "  AWS Account: $AWS_ACCOUNT_ID"
echo "  ECR Repository: $ECR_REPO"

# Step 1: Create EKS cluster
echo -e "\n${YELLOW}Step 1: Creating EKS cluster...${NC}"
if eksctl get cluster --name=$CLUSTER_NAME --region=$REGION &>/dev/null; then
    echo -e "${GREEN}Cluster already exists${NC}"
else
    eksctl create cluster \
        --name=$CLUSTER_NAME \
        --region=$REGION \
        --nodes=3 \
        --node-type=t3.medium \
        --with-oidc \
        --enable-ssm
    echo -e "${GREEN}EKS cluster created${NC}"
fi

# Step 2: Update kubeconfig
echo -e "\n${YELLOW}Step 2: Updating kubeconfig...${NC}"
aws eks update-kubeconfig --region=$REGION --name=$CLUSTER_NAME
echo -e "${GREEN}kubeconfig updated${NC}"

# Step 3: Create ECR repository
echo -e "\n${YELLOW}Step 3: Creating ECR repository...${NC}"
if aws ecr describe-repositories --repository-names=$ECR_REPO --region=$REGION 2>/dev/null | grep -q "repositoryArn"; then
    echo -e "${GREEN}ECR repository already exists${NC}"
else
    aws ecr create-repository --repository-name=$ECR_REPO --region=$REGION
    echo -e "${GREEN}ECR repository created${NC}"
fi

# Step 4: Build and push Docker image
echo -e "\n${YELLOW}Step 4: Building Docker image...${NC}"
docker build -t $ECR_REPO:latest .
echo -e "${GREEN}Docker image built${NC}"

echo -e "\n${YELLOW}Step 5: Pushing to ECR...${NC}"
aws ecr get-login-password --region=$REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
docker tag $ECR_REPO:latest $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest
echo -e "${GREEN}Image pushed to ECR${NC}"

# Step 6: Create namespace and secrets
echo -e "\n${YELLOW}Step 6: Creating namespace and secrets...${NC}"
kubectl create namespace aether || true
kubectl create secret generic aether-secrets \
    --from-literal=database-url="postgresql+asyncpg://aether:CHANGE_PASSWORD@aether-rds.c1234567.us-east-1.rds.amazonaws.com:5432/aether_db" \
    --from-literal=openai-api-key="sk-your-key-here" \
    -n aether || true
echo -e "${GREEN}Namespace and secrets created${NC}"

# Step 7: Update image in deployment manifest
echo -e "\n${YELLOW}Step 7: Updating deployment manifest...${NC}"
sed -i "s|aether-api:latest|$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest|g" k8s/api-deployment.yaml

# Step 8: Deploy Kubernetes resources
echo -e "\n${YELLOW}Step 8: Deploying Kubernetes resources...${NC}"
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/redis-statefulset.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/ingress.yaml
echo -e "${GREEN}Kubernetes resources deployed${NC}"

# Step 9: Wait for deployment
echo -e "\n${YELLOW}Step 9: Waiting for deployment to be ready...${NC}"
kubectl rollout status deployment/aether-api -n aether
echo -e "${GREEN}Deployment is ready${NC}"

# Final info
echo -e "\n${GREEN}Deployment successful!${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Update DNS: Point aether.example.com to the LoadBalancer IP"
echo "2. Get LoadBalancer IP: kubectl get service -n aether"
echo "3. Monitor: kubectl logs -n aether -f deployment/aether-api"
echo "4. Scale: kubectl scale deployment aether-api -n aether --replicas=5"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  kubectl get pods -n aether"
echo "  kubectl logs -n aether -f deployment/aether-api"
echo "  kubectl describe pod -n aether <pod-name>"
echo "  kubectl port-forward -n aether svc/aether-api 8000:8000"
