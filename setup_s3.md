# S3 Setup for Media Files

## Problem Solved
Images disappear on Render deployment because media files are stored locally and get wiped during deployments.

## Solution: AWS S3 for Media Storage

### Step 1: Create AWS S3 Bucket
1. Go to [AWS Console](https://console.aws.amazon.com/s3/)
2. Click "Create bucket"
3. **Bucket name**: `voteapp-media-files` (or your choice)
4. **Region**: US East (N. Virginia) `us-east-1`
5. **Block Public Access settings**: UNCHECK "Block all public access"
6. **Object Ownership**: ACLs enabled
7. Click "Create bucket"

### Step 2: Create IAM User
1. Go to [IAM Console](https://console.aws.amazon.com/iam/)
2. Click "Users" → "Create user"
3. **User name**: `voteapp-s3-user`
4. Click "Next"
5. **Permissions**: "Attach policies directly"
6. Add these policies:
   - `AmazonS3FullAccess`
7. Click "Next" → "Create user"

### Step 3: Get IAM Credentials
1. Click on the created user `voteapp-s3-user`
2. Go to "Security credentials" tab
3. Click "Create access key"
4. Select "Command Line Interface (CLI)"
5. Click "Next"
6. **Copy and save**:
   - Access key ID
   - Secret access key

### Step 4: Configure Render Environment Variables
1. Go to [Render Dashboard](https://render.com)
2. Select your `voteapp` service
3. Go to "Environment" tab
4. Add these environment variables:
   ```
   AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
   AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
   AWS_STORAGE_BUCKET_NAME=voteapp-media-files
   AWS_S3_REGION_NAME=us-east-1
   ```

### Step 5: Deploy
1. Commit and push changes to GitHub
2. Render will automatically redeploy
3. Test uploading images

## How It Works
- **Development**: Media files stored locally (`/media/`)
- **Production**: Media files stored on S3
- **URLs**: Images served from `https://bucket-name.s3.amazonaws.com/`
- **Persistence**: Images survive deployments

## Benefits
✅ Images persist across deployments
✅ Scalable storage solution
✅ Fast CDN delivery
✅ Cost-effective for small apps

## Testing
After deployment:
1. Upload a candidate photo in admin
2. Check if image displays correctly
3. Verify image URL points to S3
