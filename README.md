# 🎯 Aim Trainer

A modern, interactive aim training game built with Next.js and TypeScript. Improve your mouse accuracy and reaction time with this beautifully designed web-based trainer.

![Next.js](https://img.shields.io/badge/Next.js-15.5-black?style=flat&logo=next.js)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue?style=flat&logo=typescript)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38bdf8?style=flat&logo=tailwindcss)

## ✨ Features

- **🎮 Three Difficulty Levels**
  - **Easy**: Larger targets (80px), slower spawn rate, 10 points per hit
  - **Medium**: Medium targets (60px), moderate spawn rate, 15 points per hit
  - **Hard**: Small targets (40px), fast spawn rate, 25 points per hit

- **🎨 Beautiful UI/UX**
  - Gradient backgrounds with purple/pink theme
  - Smooth animations and transitions
  - Target-themed favicon
  - Responsive design

- **📊 Real-time Stats**
  - Live score tracking
  - Accuracy percentage
  - Hit counter
  - Miss counter
  - 30-second countdown timer

- **🎯 Dynamic Gameplay**
  - Targets spawn at random positions
  - Targets shrink over time (disappear if not clicked)
  - Crosshair cursor for immersive experience
  - Multiple targets can appear simultaneously

- **📈 Results Screen**
  - Final score display
  - Accuracy statistics
  - Total hits and misses
  - Options to replay or change difficulty

## 🚀 Getting Started

### Prerequisites

- Node.js 18.x or higher
- npm or yarn

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd aim_trainer
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

4. Open your browser and navigate to:
```
http://localhost:3000
```

### Build for Production

```bash
npm run build
npm start
```

## 🎮 How to Play

1. **Select Difficulty**: Choose between Easy, Medium, or Hard mode
2. **Start Game**: Click the "Start Game" button
3. **Click Targets**: Click the circular targets as they appear
4. **Avoid Misses**: Clicking outside targets counts as a miss
5. **Beat the Clock**: You have 30 seconds to score as many points as possible
6. **View Results**: See your final score, accuracy, and statistics

## 🛠️ Tech Stack

- **Framework**: [Next.js 15](https://nextjs.org/) with App Router
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **Animations**: Custom CSS animations
- **Icons**: Custom SVG favicon

## 📁 Project Structure

```
aim_trainer/
├── app/
│   ├── globals.css          # Global styles and animations
│   ├── layout.tsx            # Root layout
│   ├── page.tsx              # Home page
│   └── icon.svg              # Favicon
├── components/
│   └── AimTrainer.tsx        # Main game component
├── public/                   # Static assets
├── next.config.ts            # Next.js configuration
├── tailwind.config.ts        # Tailwind configuration
├── tsconfig.json             # TypeScript configuration
└── package.json              # Dependencies
```

## 🎯 Game Mechanics

### Target Behavior
- Targets spawn at random positions within the game area
- Each target shrinks at a rate determined by difficulty level
- Targets disappear when they shrink below minimum size
- Successfully clicking a target removes it and awards points

### Scoring System
- **Easy**: 10 points per hit
- **Medium**: 15 points per hit
- **Hard**: 25 points per hit

### Accuracy Calculation
```
Accuracy = (Total Hits / Total Clicks) × 100%
```

## 🎨 Customization

You can customize the game by modifying the `DIFFICULTY_SETTINGS` object in `components/AimTrainer.tsx`:

```typescript
const DIFFICULTY_SETTINGS = {
  easy: {
    targetSize: 80,        // Initial target size in pixels
    shrinkRate: 0.3,       // How fast targets shrink
    spawnDelay: 1200,      // Milliseconds between spawns
    gameDuration: 30,      // Game length in seconds
    pointsPerHit: 10,      // Points awarded per hit
  },
  // ... medium and hard settings
};
```

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

## 👨‍💻 Author

Built with Next.js and TypeScript

---

**Enjoy training your aim!** 🎯
