# Contributing to Raspberry Pi IDE Simulator

First off, thank you for considering contributing to the Raspberry Pi IDE Simulator! It's people like you that make this tool a great sandbox for hardware prototyping.

## How Can I Contribute?

### Reporting Bugs
If you find a bug (e.g., a simulated component acting weird, or a syntax highlighting issue), please check if an issue already exists. If not, open a new issue and include:
- A clear and descriptive title.
- Steps to reproduce the behavior.
- What you expected to happen vs what actually happened.

### Suggesting Enhancements
We always welcome suggestions for new simulated hardware components or IDE features! Please open an issue outlining:
- The hardware component or feature you want.
- How it would be used in a Python script (mock API).
- Any relevant datasheets or technical details.

## Local Development Setup

To set up your local Python environment, please refer to our [Getting Started Guide](docs/Getting-Started.md). 
    
If you'd like to understand how the codebase is structured (e.g., the Event Bus, Code Executor, and UI separation), please read our [Architecture Documentation](docs/ARCHITECTURE.md).

### Adding New Hardware Components
This project uses a flexible Plugin architecture. To add a new component:
1. Create a new Python file in `src/components/`.
2. Inherit from `BaseComponent`.
3. Use the `@register_component("MyNewComponent", color="#123456")` decorator.
4. Implement the visual rendering logic in the `redraw()` method.

See [components.md](docs/components.md) for more technical details on component lifecycles.

## Pull Request Process

1. Fork the repository and create your branch from `master`.
2. Ensure your code follows the existing style (e.g., Single Responsibility Principle).
3. Make sure any new background execution features or hardware APIs are decoupled from the Tkinter UI by using the `EventBus`.
4. Update the documentation in the `docs/` folder if you are adding new API methods or components.
5. Submit your PR with a clear summary of your changes!
