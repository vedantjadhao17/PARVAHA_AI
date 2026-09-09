import React from 'react';

interface Props {
  rawState?: string;
}

export const SignalStateVisualizer: React.FC<Props> = ({ rawState }) => {
  const isAvailable = !!rawState && rawState.trim().length > 0;
  const displayString = isAvailable ? rawState : 'N/A';
  // Use 8 circles as default if not available
  const chars = isAvailable ? rawState.split('') : Array(8).fill(' ');

  const getLightColor = (char: string) => {
    switch (char) {
      case 'G':
      case 'g':
        return 'bg-green-500 shadow-[0_0_8px_#10b981]';
      case 'y':
      case 'Y':
        return 'bg-yellow-400 shadow-[0_0_8px_#facc15]';
      case 'r':
      case 'R':
        return 'bg-red-500 shadow-[0_0_8px_#ef4444]';
      default:
        return 'bg-gray-600';
    }
  };

  return (
    <div className="bg-navy-900 p-4 rounded border border-navy-border flex flex-col space-y-3">
      <h4 className="text-sm font-semibold text-gray-400">Live Signal State</h4>
      
      {/* Lights container */}
      <div className="flex flex-wrap gap-2 items-center">
        {chars.map((char, idx) => (
          <div
            key={idx}
            className={`w-3 h-3 rounded-full ${getLightColor(char)}`}
          />
        ))}
      </div>
      
      {/* Raw string */}
      <div 
        className="flex items-center space-x-2"
        title="Raw TraCI signal state string"
      >
        <span className="text-xs text-gray-400">Raw:</span>
        <span className="text-sm font-mono text-gray-300">{displayString}</span>
      </div>

      {/* Legend */}
      <div className="flex items-center space-x-4 pt-3 border-t border-navy-border/50 text-[10px] text-gray-400">
        <div className="flex items-center space-x-1">
          <div className="w-2 h-2 rounded-full bg-green-500"></div>
          <span>Green</span>
        </div>
        <div className="flex items-center space-x-1">
          <div className="w-2 h-2 rounded-full bg-yellow-400"></div>
          <span>Yellow</span>
        </div>
        <div className="flex items-center space-x-1">
          <div className="w-2 h-2 rounded-full bg-red-500"></div>
          <span>Red</span>
        </div>
        <div className="flex items-center space-x-1">
          <div className="w-2 h-2 rounded-full bg-gray-600"></div>
          <span>Off</span>
        </div>
      </div>
    </div>
  );
};
