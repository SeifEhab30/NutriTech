import React, { useState, useEffect, useRef } from 'react';
import { getToken } from '../api/authApi';
import { BASE_URL } from '../api/config';
import './ImageRecognition.css';

const ImageRecognition = () => {
    const [selectedImage, setSelectedImage] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [result, setResult] = useState(null);
    const [showCamera, setShowCamera] = useState(false);
    const [weightsOverride, setWeightsOverride] = useState({}); // Now an object
    
    const videoRef = useRef(null);
    const streamRef = useRef(null);

    // Cleanup preview URL to avoid memory leaks
    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
            }
        };
    }, [previewUrl]);

    // Attach the camera stream once the <video> element is mounted.
    useEffect(() => {
        if (showCamera && videoRef.current && streamRef.current) {
            videoRef.current.srcObject = streamRef.current;
            videoRef.current.play().catch(err => console.error("Video play failed:", err));
        }
    }, [showCamera]);

    const startCamera = async () => {
        // First, check if the browser supports media devices
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert("Your browser does not support camera access. Please use a modern browser like Chrome, Firefox, or Safari.");
            return;
        }

        try {
            console.log("Requesting camera access...");
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });
            console.log("Camera access granted!", stream);
            streamRef.current = stream;
            // Render the <video> first; the stream is attached in the effect below
            // once the element is actually mounted (videoRef is null until then).
            setShowCamera(true);
        } catch (err) {
            console.error("Error accessing camera:", err);
            let errorMessage = "Could not access camera. ";
            
            if (err.name === 'NotAllowedError') {
                errorMessage += "Please allow camera permissions in your browser settings.";
            } else if (err.name === 'NotFoundError') {
                errorMessage += "No camera found on this device.";
            } else if (err.name === 'NotReadableError') {
                errorMessage += "Camera is in use by another application.";
            } else {
                errorMessage += "Please check your browser permissions.";
            }
            
            alert(errorMessage);
        }
    };

    const stopCamera = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        setShowCamera(false);
    };

    const capturePhoto = () => {
        if (videoRef.current) {
            const canvas = document.createElement('canvas');
            canvas.width = videoRef.current.videoWidth;
            canvas.height = videoRef.current.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(videoRef.current, 0, 0);
            
            canvas.toBlob((blob) => {
                const file = new File([blob], 'captured-photo.jpg', { type: 'image/jpeg' });
                setSelectedImage(file);
                setPreviewUrl(URL.createObjectURL(file));
                setResult(null);
                stopCamera();
            }, 'image/jpeg');
        }
    };

    const handleImageChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setSelectedImage(file);
            setPreviewUrl(URL.createObjectURL(file));
            setResult(null);
        }
    };

    const handleAnalyze = async () => {
        if (!selectedImage) return;

        setIsAnalyzing(true);
        
        const formData = new FormData();
        formData.append('image', selectedImage);
        
        // Add weights override as a JSON string. The number inputs store raw
        // strings, but the API requires numeric grams (> 0), so coerce/filter here.
        const cleanWeights = {};
        Object.entries(weightsOverride).forEach(([name, val]) => {
            const n = parseFloat(val);
            if (!isNaN(n) && n > 0) cleanWeights[name] = n;
        });
        if (Object.keys(cleanWeights).length > 0) {
            formData.append('weights', JSON.stringify(cleanWeights));
        }

        try {
            const token = getToken();
            const response = await fetch(`${BASE_URL}/detection/detect`, {
                method: 'POST',
                headers: token ? { Authorization: `Bearer ${token}` } : {},
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Analysis failed');
            }

            const data = await response.json();
            
            // Format the backend response to match UI needs
            setResult({
                foodItems: data.detections.map(d => ({
                    name: d.food_name,
                    count: d.count,
                    weight: d.total_weight_g,
                    calories: `${Math.round(d.calories.min)}-${Math.round(d.calories.max)}`,
                    protein: `${Math.round(d.protein.min)}-${Math.round(d.protein.max)}`,
                    carbs: `${Math.round(d.carbs.min)}-${Math.round(d.carbs.max)}`,
                    fats: `${Math.round(d.fat.min)}-${Math.round(d.fat.max)}`
                })),
                total: {
                    calories: `${Math.round(data.total_macros.calories.min)}-${Math.round(data.total_macros.calories.max)}`,
                    protein: `${Math.round(data.total_macros.protein.min)}-${Math.round(data.total_macros.protein.max)}`,
                    carbs: `${Math.round(data.total_macros.carbs.min)}-${Math.round(data.total_macros.carbs.max)}`,
                    fats: `${Math.round(data.total_macros.fat.min)}-${Math.round(data.total_macros.fat.max)}`
                },
                annotatedImage: `data:image/jpeg;base64,${data.annotated_image}`
            });

            // If we don't have local overrides yet, populate them with default weights from backend
            const newOverrides = { ...weightsOverride };
            data.detections.forEach(d => {
                if (!newOverrides[d.food_name]) {
                    newOverrides[d.food_name] = d.total_weight_g;
                }
            });
            setWeightsOverride(newOverrides);

        } catch (err) {
            console.error("Error analyzing image:", err);
            alert("Failed to analyze image. Make sure the backend server is running.");
        } finally {
            setIsAnalyzing(false);
        }
    };

    const handleWeightChange = (foodName, newWeight) => {
        setWeightsOverride(prev => ({
            ...prev,
            [foodName]: newWeight
        }));
    };

    const handleReset = () => {
        setSelectedImage(null);
        setPreviewUrl(null);
        setResult(null);
        setWeightsOverride({});
    };

    return (
        <div className="image-recognition-page">
            <div className="recognition-container">
                <div className="header-section">
                    <h2>AI Food Lens</h2>
                    <p>Snap a photo of your meal to get instant nutritional insights.</p>
                </div>

                <div className="content-grid">
                    <div className="upload-section">
                        {!previewUrl ? (
                            <div className="buttons-container">
                                {/* Upload Button */}
                                <div className="upload-button-wrapper">
                                    <input
                                        type="file"
                                        id="image-upload"
                                        accept="image/*"
                                        onChange={handleImageChange}
                                        hidden
                                    />
                                    <label htmlFor="image-upload" className="upload-btn">
                                        <span className="btn-icon">📁</span>
                                        <span className="btn-text">Upload Photo</span>
                                    </label>
                                </div>

                                {/* Camera Capture Button */}
                                <div className="camera-button-wrapper">
                                    <button className="camera-btn" onClick={startCamera}>
                                        <span className="btn-icon">📷</span>
                                        <span className="btn-text">Take Photo</span>
                                    </button>
                                </div>

                                {/* Camera View */}
                                {showCamera && (
                                    <div className="camera-view">
                                        <video 
                                            ref={videoRef} 
                                            autoPlay 
                                            playsInline 
                                            className="camera-video"
                                        />
                                        <div className="camera-controls">
                                            <button className="capture-btn" onClick={capturePhoto}>
                                                📸 Capture
                                            </button>
                                            <button className="cancel-btn" onClick={stopCamera}>
                                                ✕ Cancel
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="preview-box">
                                <img 
                                    src={result ? result.annotatedImage : previewUrl} 
                                    alt="Food Preview" 
                                    className="image-preview" 
                                />
                                {!result && (
                                    <button className="remove-btn" onClick={handleReset}>
                                        ✕
                                    </button>
                                )}
                            </div>
                        )}

                        {previewUrl && !result && (
                            <div className="analyze-controls">
                                <button
                                    className="analyze-btn"
                                    onClick={handleAnalyze}
                                    disabled={isAnalyzing}
                                >
                                    {isAnalyzing ? 'Analyzing...' : 'Identify Food'}
                                </button>
                            </div>
                        )}
                    </div>

                    {result && (
                        <div className="result-section">
                            <div className="result-card">
                                {result.foodItems.length > 0 ? (
                                    <>
                                        <h3>Detected Items</h3>
                                        <div className="detected-items-details">
                                            {result.foodItems.map((item, idx) => (
                                                <div key={idx} className="food-item-result">
                                                    <div className="food-item-header">
                                                        <span className="food-name">{item.name} x{item.count}</span>
                                                        <div className="weight-edit">
                                                            <input 
                                                                type="number" 
                                                                value={weightsOverride[item.name] !== undefined ? weightsOverride[item.name] : item.weight} 
                                                                onChange={(e) => handleWeightChange(item.name, e.target.value)}
                                                                className="item-weight-input"
                                                            />
                                                            <span className="unit">g</span>
                                                        </div>
                                                    </div>
                                                    <div className="item-macros">
                                                        <span>🔥 {item.calories} kcal</span>
                                                        <span>🥩 {item.protein}g P</span>
                                                        <span>🌾 {item.carbs}g C</span>
                                                        <span>🥑 {item.fats}g F</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>

                                        <div className="total-macros-section">
                                            <h3>Total Meal Macros</h3>
                                            <div className="macros-display">
                                                <div className="macro-item">
                                                    <span className="macro-val">{result.total.calories}</span>
                                                    <span className="macro-label">Kcal</span>
                                                </div>
                                                <div className="macro-item">
                                                    <span className="macro-val">{result.total.protein}g</span>
                                                    <span className="macro-label">Protein</span>
                                                </div>
                                                <div className="macro-item">
                                                    <span className="macro-val">{result.total.carbs}g</span>
                                                    <span className="macro-label">Carbs</span>
                                                </div>
                                                <div className="macro-item">
                                                    <span className="macro-val">{result.total.fats}g</span>
                                                    <span className="macro-label">Fats</span>
                                                </div>
                                            </div>
                                            
                                            <div className="action-buttons">
                                                <button 
                                                    className="update-btn" 
                                                    onClick={handleAnalyze} 
                                                    disabled={isAnalyzing}
                                                >
                                                    {isAnalyzing ? 'Updating...' : 'Update with New Weights'}
                                                </button>
                                                <button className="reset-btn" onClick={handleReset}>Scan Another</button>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="no-food-detected">
                                        <h3>No food detected</h3>
                                        <p>Sorry, we couldn't identify any food items in this image. Please try again with a clearer photo.</p>
                                        <div className="action-buttons">
                                            <button className="reset-btn" onClick={handleReset}>Try Another Photo</button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ImageRecognition;
