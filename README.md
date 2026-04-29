# Proof of Intent Protocol

A protocol for managing intentions and delegations with smart contracts and AI agents.

## Project Structure

- **contracts/**: Solidity smart contracts (Foundry project)
- **agents/**: Python AI agents for compilation, orchestration, research, and execution
- **utils/**: Utility functions for signing intents and interacting with contracts
- **config/**: Configuration files

## Setup

### Requirements

- Python 3.8+
- Foundry (for smart contracts)

### Python Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### Smart Contracts

Navigate to the contracts directory:

```bash
cd contracts
forge build
forge test
```

## License

MIT
