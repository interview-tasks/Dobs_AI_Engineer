"use client";

import { useState, useEffect, useCallback } from "react";

interface Target {
  id: number;
  x: number;
  y: number;
  size: number;
  createdAt: number;
}

interface GameStats {
  score: number;
  hits: number;
  misses: number;
  totalClicks: number;
}

type Difficulty = "easy" | "medium" | "hard";

const DIFFICULTY_SETTINGS = {
  easy: {
    targetSize: 80,
    shrinkRate: 0.3,
    spawnDelay: 1200,
    gameDuration: 30,
    pointsPerHit: 10,
  },
  medium: {
    targetSize: 60,
    shrinkRate: 0.5,
    spawnDelay: 900,
    gameDuration: 30,
    pointsPerHit: 15,
  },
  hard: {
    targetSize: 40,
    shrinkRate: 0.8,
    spawnDelay: 700,
    gameDuration: 30,
    pointsPerHit: 25,
  },
};

export default function AimTrainer() {
  const [gameState, setGameState] = useState<"menu" | "playing" | "ended">("menu");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [targets, setTargets] = useState<Target[]>([]);
  const [stats, setStats] = useState<GameStats>({
    score: 0,
    hits: 0,
    misses: 0,
    totalClicks: 0,
  });
  const [timeLeft, setTimeLeft] = useState(30);
  const [targetIdCounter, setTargetIdCounter] = useState(0);

  const settings = DIFFICULTY_SETTINGS[difficulty];

  const spawnTarget = useCallback(() => {
    const gameArea = document.getElementById("game-area");
    if (!gameArea) return;

    const rect = gameArea.getBoundingClientRect();
    const margin = settings.targetSize;

    const x = Math.random() * (rect.width - margin * 2) + margin;
    const y = Math.random() * (rect.height - margin * 2) + margin;

    setTargetIdCounter((prev) => {
      const newTarget: Target = {
        id: prev + 1,
        x,
        y,
        size: settings.targetSize,
        createdAt: Date.now(),
      };
      setTargets((prevTargets) => [...prevTargets, newTarget]);
      return prev + 1;
    });
  }, [settings.targetSize]);

  const handleTargetClick = (targetId: number) => {
    setTargets((prev) => prev.filter((t) => t.id !== targetId));
    setStats((prev) => ({
      ...prev,
      score: prev.score + settings.pointsPerHit,
      hits: prev.hits + 1,
      totalClicks: prev.totalClicks + 1,
    }));
  };

  const handleMissClick = () => {
    setStats((prev) => ({
      ...prev,
      misses: prev.misses + 1,
      totalClicks: prev.totalClicks + 1,
    }));
  };

  const startGame = () => {
    setGameState("playing");
    setStats({ score: 0, hits: 0, misses: 0, totalClicks: 0 });
    setTargets([]);
    setTimeLeft(settings.gameDuration);
    setTargetIdCounter(0);
  };

  const resetGame = () => {
    setGameState("menu");
    setTargets([]);
    setStats({ score: 0, hits: 0, misses: 0, totalClicks: 0 });
  };

  // Game timer
  useEffect(() => {
    if (gameState !== "playing") return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          setGameState("ended");
          setTargets([]);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [gameState]);

  // Target spawning
  useEffect(() => {
    if (gameState !== "playing") return;

    const spawnInterval = setInterval(() => {
      spawnTarget();
    }, settings.spawnDelay);

    // Spawn first target immediately
    spawnTarget();

    return () => clearInterval(spawnInterval);
  }, [gameState, spawnTarget, settings.spawnDelay]);

  // Target shrinking and removal
  useEffect(() => {
    if (gameState !== "playing") return;

    const shrinkInterval = setInterval(() => {
      setTargets((prev) =>
        prev
          .map((target) => ({
            ...target,
            size: target.size - settings.shrinkRate,
          }))
          .filter((target) => target.size > 10)
      );
    }, 50);

    return () => clearInterval(shrinkInterval);
  }, [gameState, settings.shrinkRate]);

  const accuracy = stats.totalClicks > 0
    ? ((stats.hits / stats.totalClicks) * 100).toFixed(1)
    : "0.0";

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4">
      <div className="w-full max-w-6xl">
        {gameState === "menu" && (
          <div className="text-center space-y-8 animate-fade-in">
            <div className="space-y-4">
              <h1 className="text-6xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
                Aim Trainer
              </h1>
              <p className="text-xl text-gray-300">
                Click targets quickly and accurately
              </p>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-semibold text-white">
                Select Difficulty
              </h2>
              <div className="flex gap-4 justify-center">
                {(["easy", "medium", "hard"] as Difficulty[]).map((diff) => (
                  <button
                    key={diff}
                    onClick={() => setDifficulty(diff)}
                    className={`px-8 py-4 rounded-xl font-semibold text-lg transition-all transform hover:scale-105 ${
                      difficulty === diff
                        ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg shadow-purple-500/50"
                        : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                    }`}
                  >
                    {diff.charAt(0).toUpperCase() + diff.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={startGame}
              className="px-12 py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-xl font-bold rounded-xl shadow-lg shadow-green-500/50 hover:shadow-green-500/70 transition-all transform hover:scale-105"
            >
              Start Game
            </button>
          </div>
        )}

        {gameState === "playing" && (
          <div className="space-y-4">
            {/* Game HUD */}
            <div className="flex justify-between items-center bg-black/30 backdrop-blur-sm rounded-xl p-6 border border-purple-500/30">
              <div className="flex gap-8">
                <div className="text-center">
                  <div className="text-gray-400 text-sm">Score</div>
                  <div className="text-3xl font-bold text-white">{stats.score}</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400 text-sm">Accuracy</div>
                  <div className="text-3xl font-bold text-green-400">{accuracy}%</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400 text-sm">Hits</div>
                  <div className="text-3xl font-bold text-blue-400">{stats.hits}</div>
                </div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-sm">Time Left</div>
                <div className={`text-4xl font-bold ${timeLeft <= 5 ? 'text-red-400 animate-pulse' : 'text-white'}`}>
                  {timeLeft}s
                </div>
              </div>
            </div>

            {/* Game Area */}
            <div
              id="game-area"
              onClick={handleMissClick}
              className="relative w-full h-[600px] bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl border-4 border-purple-500/50 shadow-2xl overflow-hidden cursor-crosshair"
            >
              {targets.map((target) => (
                <div
                  key={target.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleTargetClick(target.id);
                  }}
                  className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-all animate-target-appear"
                  style={{
                    left: `${target.x}px`,
                    top: `${target.y}px`,
                    width: `${target.size}px`,
                    height: `${target.size}px`,
                  }}
                >
                  {/* Outer ring */}
                  <div className="absolute inset-0 rounded-full bg-gradient-to-br from-red-500 to-pink-600 animate-pulse" />
                  {/* Middle ring */}
                  <div className="absolute inset-[15%] rounded-full bg-gradient-to-br from-white to-red-200" />
                  {/* Center dot */}
                  <div className="absolute inset-[40%] rounded-full bg-gradient-to-br from-red-600 to-red-800" />
                </div>
              ))}
            </div>
          </div>
        )}

        {gameState === "ended" && (
          <div className="text-center space-y-8 animate-fade-in">
            <div className="space-y-4">
              <h1 className="text-5xl font-bold bg-gradient-to-r from-yellow-400 to-orange-500 bg-clip-text text-transparent">
                Game Over!
              </h1>
              <p className="text-xl text-gray-300">Here are your results</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto">
              <div className="bg-gradient-to-br from-purple-600 to-purple-800 p-6 rounded-xl shadow-xl">
                <div className="text-gray-200 text-sm mb-2">Final Score</div>
                <div className="text-4xl font-bold text-white">{stats.score}</div>
              </div>
              <div className="bg-gradient-to-br from-green-600 to-green-800 p-6 rounded-xl shadow-xl">
                <div className="text-gray-200 text-sm mb-2">Accuracy</div>
                <div className="text-4xl font-bold text-white">{accuracy}%</div>
              </div>
              <div className="bg-gradient-to-br from-blue-600 to-blue-800 p-6 rounded-xl shadow-xl">
                <div className="text-gray-200 text-sm mb-2">Total Hits</div>
                <div className="text-4xl font-bold text-white">{stats.hits}</div>
              </div>
              <div className="bg-gradient-to-br from-orange-600 to-orange-800 p-6 rounded-xl shadow-xl">
                <div className="text-gray-200 text-sm mb-2">Misses</div>
                <div className="text-4xl font-bold text-white">{stats.misses}</div>
              </div>
            </div>

            <div className="flex gap-4 justify-center">
              <button
                onClick={startGame}
                className="px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-xl font-bold rounded-xl shadow-lg shadow-green-500/50 hover:shadow-green-500/70 transition-all transform hover:scale-105"
              >
                Play Again
              </button>
              <button
                onClick={resetGame}
                className="px-8 py-4 bg-gradient-to-r from-gray-600 to-gray-700 text-white text-xl font-bold rounded-xl shadow-lg hover:shadow-gray-500/50 transition-all transform hover:scale-105"
              >
                Change Difficulty
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
