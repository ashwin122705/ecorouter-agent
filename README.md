# EcoRouter: LLM Agentic Carbon Scheduler 🌱 🤖

**Stanford CS 153 (Frontier Systems) - Spring 2026 Final Project**
*Project Prompt: The One-Person Frontier Lab. Scale yourself using modern AI tools to do the work of an organization.*

## 📌 Project Overview

As AI scales, the energy constraints and carbon footprints of data centers are becoming the primary bottleneck for the industry. Currently, optimizing where and when AI workloads run requires a dedicated DevOps and FinOps team. 

**EcoRouter** simulates an autonomous LLM agent that acts as a global infrastructure manager. Instead of routing batch jobs (like model fine-tuning) based purely on default settings, the EcoRouter agent analyzes simulated real-time grid data and dynamically routes workloads to data centers powered by the greenest energy—while respecting user deadlines and data privacy constraints.

## 🏗️ Architecture

This project is built as a pure-software "digital twin" simulation, utilizing an LLM Tool-Calling architecture. 

1. **The Grid Simulation:** Generates a live, fluctuating global cloud network (e.g., US-East, Europe-West) with varying carbon intensities (gCO₂/kWh) and a queue of mock AI computing jobs.
2. **The LLM Brain:** A multi-agent system powered by LLM Function Calling. It evaluates the job queue, calls tools to check regional grid statuses, reasons about the optimal location and time, and executes the assignment.
3. **The Proof:** A Streamlit dashboard that visualizes the agent's real-time routing decisions and calculates the theoretical carbon saved compared to a standard baseline scheduler.

## 🚀 Getting Started

### Prerequisites
* Python 3.9+
* An API Key from an LLM provider (OpenAI, Anthropic, or Google Gemini)

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/ashwin122705/ecorouter-agent.git](https://github.com/ashwin122705/ecorouter-agent.git)
   cd ecorouter-agent
