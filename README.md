# homelab-ansible

English | [日本語](README.ja.md)

This repository is an Ansible automation project designed for a personal homelab environment.

Its goal is to build a sustainable approach to security, operations, and backup management with the assistance of AI.

However, this project is not intended to be merely a collection of Ansible playbooks.

Cyber threats continue to evolve rapidly. Today, even home users need to think about security controls, certificate management, backup operations, and continuous patch management.

At the same time, designing, implementing, and maintaining these capabilities as an individual is not easy.

This project explores how AI can help make enterprise-inspired operational practices achievable in a personal environment.

AI-Assisted Development Approach

This project uses multiple AI systems during implementation and review.

* One AI proposes implementations
* Another AI performs reviews
* Different AI systems cross-check each other
* Final decisions are always made by a human

AI is not the decision maker.

AI serves as an assistant, while responsibility for code quality, security, and operational decisions remains with the human operator.

Instead of relying solely on a traditional Issue / Pull Request workflow, this repository stores requirements, implementation records, and review documents as part of the project history.

This makes it possible to trace:

* Design decisions
* AI discussions
* Review findings
* Implementation changes
* Improvement history

Even users who are not deeply familiar with Git can follow the evolution of a feature and understand how AI-assisted development can improve design quality and code quality over time.

AI-Assisted Operations

AI is also used to support patch management.

In personal environments, patching often depends on manual decisions and inconsistent processes.

To address this, patch classification rules and deployment criteria are defined by a human in advance. AI then analyzes update information and summarizes the potential operational and security impact according to those predefined rules.

AI never decides whether updates should be installed.

The final decision always belongs to the operator.

Following human-defined operational policies, AI organizes information such as:

* Urgency
* Risk level
* Impact scope
* Decision-making factors

The objective is to provide information in a format that helps operators make informed decisions more efficiently.

Repository Structure

```text
homelab-ansible/
├── inventories/         # Inventory definitions and variables
├── playbooks/           # Entry point playbooks
├── roles/               # Reusable Ansible roles
├── reports/             # Generated reports and summaries
├── scripts/             # Utility scripts
├── docs/
│   └── ai/
│       ├── prompts/     # AI design and implementation policies
│       └── reviews/     # Requirement / Implement / Review history
├── README.md            # English documentation
├── README.ja.md         # Japanese documentation
└── LICENSE
```

The `docs/ai/reviews` directory contains the requirement, implementation,
and review history used during development.

Instead of relying solely on Issues and Pull Requests, the project preserves
AI-assisted design decisions and review records as documentation.

Technologies Covered

This project actively incorporates technologies that are expected to become increasingly important for home users.

* WPA3 Enterprise
* FreeRADIUS
* EAP-TLS
* SSL/TLS Certificate Management
* Passwordless Authentication
* Certificate-Based VPN Authentication
* Automated Patch Management
* Backup Verification
* Continuous Health Monitoring
* Infrastructure Automation

While this repository focuses on Ansible automation, it is intended to complement the accompanying blog and help home users improve both security awareness and practical IT skills.

Blog

Detailed articles about homelab architecture, operations, and security are available on the blog:

https://yoshi0808.github.io/new-technology/

The long-term goal is to make operational practices that were traditionally associated with enterprise environments sustainable and achievable for individuals through the practical use of AI.

Main Features

* Proxmox Cluster Health Check
* Proxmox Automated Patch Workflow
* FreeRADIUS Monitoring
* Certificate Renewal
* UniFi Backup Collection
* Backup Restore Verification
* Slack Notifications

Why This Repository Exists

The purpose of this project is not simply to generate code with AI.

Its purpose is to build sustainable solutions for the operational and security challenges that home users face.

AI is not a replacement for the operator.

Humans make decisions.
Humans remain accountable.

This repository is published as a practical example of how AI can be used to support responsible infrastructure operations in a personal environment.
