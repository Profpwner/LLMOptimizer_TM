import React, { useRef, useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  IconButton,
  useTheme,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import {
  MoreVert as MoreVertIcon,
  Fullscreen as FullscreenIcon,
  Replay as ResetIcon,
} from '@mui/icons-material';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Line } from '@react-three/drei';
import * as THREE from 'three';
import { useAppDispatch } from '../../hooks/redux';
import { setFullscreenWidget } from '../../store/slices/dashboardSlice';

interface Node {
  id: string;
  label: string;
  position: [number, number, number];
  size: number;
  color: string;
  connections: string[];
}

interface NetworkNodeProps {
  node: Node;
  onHover: (id: string | null) => void;
  onClick: (id: string) => void;
  isHighlighted: boolean;
  isSelected: boolean;
}

const NetworkNode: React.FC<NetworkNodeProps> = ({ node, onHover, onClick, isHighlighted, isSelected }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  useFrame((state) => {
    if (meshRef.current) {
      const scale = hovered || isHighlighted ? 1.2 : 1;
      meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.1);
      
      if (isSelected) {
        meshRef.current.rotation.y += 0.01;
      }
    }
  });

  return (
    <group position={node.position}>
      <mesh
        ref={meshRef}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          onHover(node.id);
        }}
        onPointerOut={(e) => {
          e.stopPropagation();
          setHovered(false);
          onHover(null);
        }}
        onClick={(e) => {
          e.stopPropagation();
          onClick(node.id);
        }}
      >
        <sphereGeometry args={[node.size, 32, 16]} />
        <meshStandardMaterial
          color={node.color}
          emissive={node.color}
          emissiveIntensity={isHighlighted || isSelected ? 0.5 : 0.1}
          metalness={0.3}
          roughness={0.4}
        />
      </mesh>
      <Text
        position={[0, node.size + 0.5, 0]}
        fontSize={0.3}
        color="white"
        anchorX="center"
        anchorY="middle"
      >
        {node.label}
      </Text>
    </group>
  );
};

interface NetworkEdgeProps {
  start: [number, number, number];
  end: [number, number, number];
  isHighlighted: boolean;
}

const NetworkEdge: React.FC<NetworkEdgeProps> = ({ start, end, isHighlighted }) => {
  const theme = useTheme();
  
  return (
    <Line
      points={[start, end]}
      color={isHighlighted ? theme.palette.primary.light : theme.palette.divider}
      lineWidth={isHighlighted ? 3 : 1}
      opacity={isHighlighted ? 1 : 0.3}
      transparent
    />
  );
};

interface Network3DProps {
  widgetId: string;
  config: {
    title?: string;
    nodes?: Node[];
    viewMode?: '3d' | 'force' | 'hierarchy';
    showLabels?: boolean;
    animationSpeed?: number;
  };
}

const Network3D: React.FC<Network3DProps> = ({ widgetId, config }) => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState(config.viewMode || '3d');

  const handleFullscreen = () => {
    dispatch(setFullscreenWidget(widgetId));
  };

  const nodes: Node[] = config.nodes || [
    { id: '1', label: 'Main Topic', position: [0, 0, 0], size: 0.8, color: '#1976d2', connections: ['2', '3', '4'] },
    { id: '2', label: 'Subtopic A', position: [3, 1, 0], size: 0.6, color: '#dc004e', connections: ['5', '6'] },
    { id: '3', label: 'Subtopic B', position: [-3, 1, 0], size: 0.6, color: '#9c27b0', connections: ['7'] },
    { id: '4', label: 'Subtopic C', position: [0, -2, 2], size: 0.6, color: '#2e7d32', connections: ['8', '9'] },
    { id: '5', label: 'Detail A1', position: [5, 2, 1], size: 0.4, color: '#ed6c02', connections: [] },
    { id: '6', label: 'Detail A2', position: [4, 0, -1], size: 0.4, color: '#ed6c02', connections: [] },
    { id: '7', label: 'Detail B1', position: [-5, 2, 0], size: 0.4, color: '#0288d1', connections: [] },
    { id: '8', label: 'Detail C1', position: [1, -3, 3], size: 0.4, color: '#d32f2f', connections: [] },
    { id: '9', label: 'Detail C2', position: [-1, -3, 2], size: 0.4, color: '#d32f2f', connections: [] },
  ];

  const edges = useMemo(() => {
    const edgeList: { start: [number, number, number]; end: [number, number, number]; nodes: string[] }[] = [];
    nodes.forEach((node) => {
      node.connections.forEach((targetId) => {
        const targetNode = nodes.find((n) => n.id === targetId);
        if (targetNode) {
          edgeList.push({
            start: node.position,
            end: targetNode.position,
            nodes: [node.id, targetId],
          });
        }
      });
    });
    return edgeList;
  }, [nodes]);

  const isNodeHighlighted = (nodeId: string) => {
    if (!hoveredNode && !selectedNode) return false;
    const activeNode = selectedNode || hoveredNode;
    if (nodeId === activeNode) return true;
    const node = nodes.find((n) => n.id === activeNode);
    return node ? node.connections.includes(nodeId) : false;
  };

  const isEdgeHighlighted = (edgeNodes: string[]) => {
    if (!hoveredNode && !selectedNode) return false;
    const activeNode = selectedNode || hoveredNode;
    return activeNode ? edgeNodes.includes(activeNode) : false;
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box
        className="widget-header"
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          pb: 0,
          cursor: 'move',
        }}
      >
        <Typography variant="h6">{config.title || '3D Semantic Network'}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(e, newMode) => newMode && setViewMode(newMode)}
            size="small"
          >
            <ToggleButton value="3d">3D</ToggleButton>
            <ToggleButton value="force">Force</ToggleButton>
            <ToggleButton value="hierarchy">Tree</ToggleButton>
          </ToggleButtonGroup>
          <IconButton size="small" onClick={() => setSelectedNode(null)}>
            <ResetIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={handleFullscreen}>
            <FullscreenIcon fontSize="small" />
          </IconButton>
          <IconButton size="small">
            <MoreVertIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <CardContent sx={{ flexGrow: 1, p: 0 }}>
        <Box sx={{ width: '100%', height: '100%', position: 'relative' }}>
          <Canvas
            camera={{ position: [5, 5, 5], fov: 60 }}
            style={{
              background: theme.palette.mode === 'dark' 
                ? 'radial-gradient(ellipse at center, #1a237e 0%, #000051 100%)'
                : 'radial-gradient(ellipse at center, #e3f2fd 0%, #bbdefb 100%)',
            }}
          >
            <ambientLight intensity={0.5} />
            <pointLight position={[10, 10, 10]} intensity={0.8} />
            <pointLight position={[-10, -10, -10]} intensity={0.4} />
            
            {/* Render edges */}
            {edges.map((edge, index) => (
              <NetworkEdge
                key={index}
                start={edge.start}
                end={edge.end}
                isHighlighted={isEdgeHighlighted(edge.nodes)}
              />
            ))}
            
            {/* Render nodes */}
            {nodes.map((node) => (
              <NetworkNode
                key={node.id}
                node={node}
                onHover={setHoveredNode}
                onClick={setSelectedNode}
                isHighlighted={isNodeHighlighted(node.id)}
                isSelected={selectedNode === node.id}
              />
            ))}
            
            <OrbitControls
              enablePan={true}
              enableZoom={true}
              enableRotate={true}
              autoRotate={!hoveredNode && !selectedNode}
              autoRotateSpeed={0.5}
            />
          </Canvas>
          
          {/* Info overlay */}
          {(hoveredNode || selectedNode) && (
            <Box
              sx={{
                position: 'absolute',
                top: 16,
                left: 16,
                backgroundColor: theme.palette.background.paper,
                borderRadius: 1,
                p: 2,
                boxShadow: theme.shadows[4],
                maxWidth: 200,
              }}
            >
              <Typography variant="subtitle2" gutterBottom>
                {selectedNode ? 'Selected' : 'Hovering'}
              </Typography>
              <Typography variant="body2">
                {nodes.find((n) => n.id === (selectedNode || hoveredNode))?.label}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Connections: {nodes.find((n) => n.id === (selectedNode || hoveredNode))?.connections.length || 0}
              </Typography>
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

export default Network3D;