# 🌐 AgriPredict Distributed Storage

A secure, distributed file storage system where users see **ONE simple interface** while files are automatically split across multiple nodes for redundancy.

## ✨ Features

- **Simple User Interface**: Users only see "You have 2.5GB storage"
- **Automatic Distribution**: Files split into 2MB blocks across 5 nodes
- **Fault Tolerant**: If one node fails, files can still be recovered
- **Secure**: Files distributed, not stored in one place
- **Modern UI**: Beautiful, responsive interface with drag & drop

## 📊 Storage Architecture

- **Total User Storage**: 2.5GB
- **Number of Nodes**: 5 (hidden from user)
- **Storage per Node**: 500MB
- **Block Size**: 2MB
- **Location**: `~/AgriPredict_Distributed_Storage/`

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt