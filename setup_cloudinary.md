# Cloudinary Setup for Candidate Images & Media Files

## Overview
This application uses **Cloudinary** for storing and delivering uploaded candidate photos. Images persist across deployments (e.g. on Render, Heroku, Railway) with automatic CDN optimization.

---

## Step 1: Create a Free Cloudinary Account
1. Go to [Cloudinary Sign Up](https://cloudinary.com/users/register_free).
2. Create a free account (includes generous monthly storage and bandwidth).

---

## Step 2: Get Your Cloudinary Credentials
1. In your [Cloudinary Dashboard / Console](https://console.cloudinary.com/):
2. Copy the following keys:
   - **Cloud Name**: `your_cloud_name`
   - **API Key**: `your_api_key`
   - **API Secret**: `your_api_secret`
   - (Or copy the single **API Environment variable / URL**: `CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>`)

---

## Step 3: Configure Environment Variables

### In Production (e.g., Render Dashboard):
1. Navigate to your web service settings.
2. Under the **Environment** tab, add:
   ```env
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```
   *(Or alternatively: `CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME`)*

### In Local Development (`.env` file, optional):
If you want to test Cloudinary locally, add the variables above to your `.env` file. If omitted locally, media uploads automatically fall back to the local `media/` directory.

---

## How It Works
- **Local Dev without Cloudinary**: Uploads saved to `/media/voter_candidate/` on your machine.
- **Production / Configured (Cloudinary)**: Uploads are automatically saved in the `voter_candidate` folder in your Cloudinary media library and served via high-speed global CDN links.
- **Persistence**: Candidate photos survive server rebuilds and redeployments seamlessly.
