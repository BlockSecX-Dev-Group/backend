BlockSecArena Backend System
📖 Introduction
BlockSecArena is the core backend system for a decentralized Web3 security education and CTF (Capture The Flag) competition platform.

Built on the Python Flask framework, this project deeply integrates Web3 interaction logic. The system primarily handles off-chain business logic, including decentralized user identity authentication, course progress tracking, CTF range state management, off-chain signature verification (EIP-712), and automated distribution of NFT credentials. It aims to provide users with a closed-loop experience ranging from theoretical learning to practical combat exercises.

✨ Key Features
1. 🔐 User & Authentication System
Wallet Connect: Supports direct login via Ethereum/EVM-compatible wallet addresses.
JWT Authentication: Utilizes stateless JWT mechanisms to manage user sessions and permissions.
User Profile: Tracks user learning paths, points (UserPoints), and on-chain interaction history.

2. 📺 Interactive Learning Module
Course Flow Management: Manages video metadata and chapter sequence control (VideoSequence).
Unlock Mechanism: Implements time-based anti-cheat logic to ensure users complete prerequisite courses before advancing.
State Tracking: Records user watch progress, completion status, and reward claim status.

3. 🚩 CTF Competition & Challenges
Range Management: Dynamically manages the startup and recycling of Docker containerized CTF ranges.
Daily Challenges: A randomly generated blockchain security knowledge quiz system.
Flag Verification: Automatically validates CTF submissions and executes point settlements.

4. ⛓️ Web3 & Blockchain Integration
EIP-712 Signatures: Implements secure off-chain signature logic, allowing users to mint NFTs for free via signatures (Gasless Minting).
NFT Credentials: Puts learning achievements on-chain and automatically records NFT minting status (NFTMintRecord).
Token Interaction: Logic for the exchange and distribution of Points and ERC-20 tokens.

🛠 Tech Stack
Backend Framework: Python Flask
Database: MySQL / MariaDB (with SQLAlchemy ORM)
Web3 Tools: Web3.py, eth-account, EIP-712 Type definitions
Task Scheduling: APScheduler (Handles range timeout recycling, periodic settlements)
API Standard: RESTful API

📂 Directory Structure
Plaintext

backend/
├── backend/
│   ├── main.py                 # 服务启动入口
│   ├── requirements.txt        # 项目依赖
│   ├── main/
│   │   ├── models/             # 数据模型定义 (ORM)
│   │   │   ├── UserData.py
│   │   │   ├── VideoInfo.py
│   │   │   └── ...
│   │   ├── managers/           # 核心业务逻辑层
│   │   │   ├── NFTManager.py   # 签名与铸造逻辑
│   │   │   ├── GameManager.py  # 游戏进度控制
│   │   │   └── ...
│   │   ├── services/           # 外部服务集成
│   │   └── utils/              # 通用工具类
└── README.md

🚀 Deployment Guide
1. Prerequisites
Python: 3.8+
Database: MySQL 5.7+ or MariaDB
Blockchain Network: Deployed on BNB Chain
