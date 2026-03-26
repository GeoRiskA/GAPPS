# fiducial_detection_dl.py
import os
import cv2
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib
import matplotlib
matplotlib.use('TkAgg')  # Use non-interactive backend for saving plots
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split

def extract_image_features(image, size=(64, 64)):
    """
    Extract features from image for machine learning

    :param image: Input image
    :param size: Size to resize to
    :return: Feature vector
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Resize to fixed size
    resized = cv2.resize(gray, size)

    # Extract HOG features
    # Simple alternative: just use pixel values
    features = resized.flatten() / 255.0

    return features

def prepare_training_data_from_csv(fiducial_csv_path, images_folder, output_folder):
    """
    Prepare training data from existing fiducial mark annotations

    :param fiducial_csv_path: Path to CSV with fiducial mark coordinates
    :param images_folder: Folder containing original images
    :param output_folder: Folder to save training data
    """
    # Create output folder
    os.makedirs(output_folder, exist_ok=True)

    # Load annotations
    df = pd.read_csv(fiducial_csv_path)

    # Prepare output annotation file
    annotations = []

    # Process each image
    for _, row in df.iterrows():
        image_name = row['name']
        image_path = os.path.join(images_folder, image_name + '.tif')

        if not os.path.exists(image_path):
            # Try alternative extensions
            for ext in ['.jpg', '.png', '.tiff']:
                alt_path = os.path.join(images_folder, image_name + ext)
                if os.path.exists(alt_path):
                    image_path = alt_path
                    break

        if not os.path.exists(image_path):
            print(f"Image not found: {image_name}")
            continue

        # Load image
        img = cv2.imread(image_path)
        if img is None:
            print(f"Failed to load image: {image_path}")
            continue

        # Extract fiducial regions with coordinates
        corners = {
            'top_left': (row['X1'], row['Y1']),
            'top_right': (row['X2'], row['Y2']),
            'bot_right': (row['X3'], row['Y3']),
            'bot_left': (row['X4'], row['Y4'])
        }

        # Extract and save each corner
        for corner, (x, y) in corners.items():
            # Extract a region around the fiducial
            size = 500  # Size of extraction window
            try:
                x, y = int(float(x)), int(float(y))
            except (ValueError, TypeError):
                print(f"Invalid coordinates for {image_name}, {corner}: {x}, {y}")
                continue

            # Ensure within image bounds
            x1 = max(0, x - size//2)
            y1 = max(0, y - size//2)
            x2 = min(img.shape[1], x + size//2)
            y2 = min(img.shape[0], y + size//2)

            # Extract region
            region = img[y1:y2, x1:x2]

            # Skip if region is empty
            if region.size == 0:
                print(f"Empty region for {image_name}, {corner}")
                continue

            # Adjust coordinates to be relative to the extracted region
            rel_x = x - x1
            rel_y = y - y1

            # Save region
            region_name = f"{image_name}_{corner}.jpg"
            region_path = os.path.join(output_folder, region_name)
            cv2.imwrite(region_path, region)

            # Add to annotations
            annotations.append({
                'image_name': region_name,
                'x': rel_x,
                'y': rel_y,
                'corner': corner
            })

    # Save annotations
    pd.DataFrame(annotations).to_csv(os.path.join(output_folder, 'annotations.csv'), index=False)

    print(f"Prepared {len(annotations)} training samples in {output_folder}")
    return os.path.join(output_folder, 'annotations.csv')

def train_fiducial_model(training_data_folder, annotations_file, output_model_path, model='RF'):
    """
    Train machine learning model for fiducial detection

    :param training_data_folder: Folder with training images
    :param annotations_file: Path to annotations CSV
    :param output_model_path: Path to save model
    :param model: Model type ('RF' or 'GB')
    """
    # Load annotations
    annotations = pd.read_csv(annotations_file)

    # Prepare features and targets
    X = []  # Features
    y_coords = []  # Targets (x, y coordinates)
    corners = []  # Store corner types

    for _, row in annotations.iterrows():
        img_path = os.path.join(training_data_folder, row['image_name'])
        if not os.path.exists(img_path):
            continue

        # Load image
        img = cv2.imread(img_path)
        if img is None:
            continue

        # Extract features
        features = extract_image_features(img) if model == 'RF' else extract_enhanced_features(img)

        # Add to dataset
        X.append(features)
        y_coords.append([row['x'], row['y']])
        corners.append(row['corner'])

    # Convert to numpy arrays
    X = np.array(X)
    y_coords = np.array(y_coords)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y_coords, test_size=0.2, random_state=42)

    if model == 'RF':
        # Train RandomForest model (handles multi-output)
        print("Training Random Forest model...")
        rf_model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        rf_model.fit(X_train, y_train)

        # Evaluate model
        train_score = rf_model.score(X_train, y_train)
        test_score = rf_model.score(X_test, y_test)

        print(f"Model performance: Train R² = {train_score:.4f}, Test R² = {test_score:.4f}")

        # Save model
        os.makedirs(os.path.dirname(output_model_path), exist_ok=True)
        joblib.dump(rf_model, output_model_path)

        # Plot results
        y_pred = rf_model.predict(X_test)

        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        plt.scatter(y_test[:, 0], y_pred[:, 0])
        plt.plot([0, 500], [0, 500], 'r--')
        plt.xlabel('True X')
        plt.ylabel('Predicted X')
        plt.title('X Coordinate Prediction')

        plt.subplot(1, 2, 2)
        plt.scatter(y_test[:, 1], y_pred[:, 1])
        plt.plot([0, 500], [0, 500], 'r--')
        plt.xlabel('True Y')
        plt.ylabel('Predicted Y')
        plt.title('Y Coordinate Prediction')

        plt.tight_layout()
        plt.savefig(os.path.join(os.path.dirname(output_model_path), 'model_performance_RF.png'))

        print(f"Model saved to {output_model_path}")
        return rf_model

    elif model == 'GB':
        from sklearn.ensemble import GradientBoostingRegressor

        # For GB, need separate models for x and y coordinates
        print("Training Gradient Boosting models for X and Y coordinates...")

        # Split target into separate x and y arrays
        y_x = y_coords[:, 0]  # X coordinates
        y_y = y_coords[:, 1]  # Y coordinates

        # Dictionary to store models by corner type
        corner_models = {}

        # Train specialized models for each corner type
        for corner_type in set(corners):
            # Get indices for this corner type
            indices = [i for i, c in enumerate(corners) if c == corner_type]
            if len(indices) < 5:  # Skip if too few samples
                print(f"Skipping {corner_type}: too few samples ({len(indices)})")
                continue

            print(f"Training model for {corner_type} corner...")

            # Get data for this corner type
            X_corner = X[indices]
            y_x_corner = y_x[indices]
            y_y_corner = y_y[indices]

            # Train X coordinate model
            gb_x = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=5, random_state=42)
            gb_x.fit(X_corner, y_x_corner)

            # Train Y coordinate model
            gb_y = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=5, random_state=42)
            gb_y.fit(X_corner, y_y_corner)

            # Store models
            corner_models[corner_type] = {'x_model': gb_x, 'y_model': gb_y}

        # Train general models as fallback
        print("Training general models...")
        general_x_model = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=5, random_state=42)
        general_x_model.fit(X, y_x)

        general_y_model = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=5, random_state=42)
        general_y_model.fit(X, y_y)

        # Evaluate general models
        x_score = general_x_model.score(X_test, y_test[:, 0])
        y_score = general_y_model.score(X_test, y_test[:, 1])
        print(f"General model performance: X-coord R² = {x_score:.4f}, Y-coord R² = {y_score:.4f}")

        # Save all models
        models = {
            'corner_models': corner_models,
            'general_models': {
                'x_model': general_x_model,
                'y_model': general_y_model
            }
        }

        os.makedirs(os.path.dirname(output_model_path), exist_ok=True)
        joblib.dump(models, output_model_path)

        # Plot results for general model
        x_pred = general_x_model.predict(X_test)
        y_pred = general_y_model.predict(X_test)

        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        plt.scatter(y_test[:, 0], x_pred)
        plt.plot([0, 500], [0, 500], 'r--')
        plt.xlabel('True X')
        plt.ylabel('Predicted X')
        plt.title('X Coordinate Prediction')

        plt.subplot(1, 2, 2)
        plt.scatter(y_test[:, 1], y_pred)
        plt.plot([0, 500], [0, 500], 'r--')
        plt.xlabel('True Y')
        plt.ylabel('Predicted Y')
        plt.title('Y Coordinate Prediction')

        plt.tight_layout()
        plt.savefig(os.path.join(os.path.dirname(output_model_path), 'model_performance_GB.png'))

        print(f"Models saved to {output_model_path}")
        return models
def detect_fiducial_rf(corner_image, model_path, corner=None, image_name=None):
    """
    Detect fiducial mark using trained random forest model

    :param corner_image: Cropped corner image
    :param model_path: Path to trained model
    :param corner: Corner identifier
    :param image_name: Image name
    :return: x, y coordinates and confidence
    """
    # Load model
    model = joblib.load(model_path)

    # Extract features
    features = extract_image_features(corner_image)

    # Make prediction
    prediction = model.predict([features])[0]

    # Get confidence from prediction error of trees
    predictions = np.array([tree.predict([features])[0] for tree in model.estimators_])
    std_dev = np.std(predictions, axis=0)
    max_std = np.max(std_dev)

    # Convert std dev to confidence (lower std dev = higher confidence)
    confidence = max(0, min(1, 1.0 - (max_std / 50.0)))

    x, y = int(prediction[0]), int(prediction[1])

    print(f"RF detection: ({x}, {y}) with confidence {confidence:.2f}")

    # Visualization for debugging
    debug_img = corner_image.copy()
    cv2.circle(debug_img, (x, y), 5, (0, 255, 0), -1)

    # Create debug folder
    debug_folder = os.path.join(os.path.dirname(model_path), 'debug_predictions')
    os.makedirs(debug_folder, exist_ok=True)

    # Save debug image
    debug_name = f"{image_name}_{corner}_pred.jpg" if image_name and corner else "prediction.jpg"
    cv2.imwrite(os.path.join(debug_folder, debug_name), debug_img)

    return x, y, confidence

def detect_fiducial_gb(corner_image, model_path, corner=None, image_name=None):
    """
    Detect fiducial mark using trained gradient boosting models

    :param corner_image: Cropped corner image
    :param model_path: Path to trained model
    :param corner: Corner identifier (e.g., 'top_left')
    :param image_name: Image name
    :return: x, y coordinates and confidence
    """
    # Load models
    models = joblib.load(model_path)
    corner_models = models['corner_models']
    general_models = models['general_models']

    # Extract features
    features = extract_enhanced_features(corner_image)

    # Choose appropriate models
    if corner in corner_models:
        x_model = corner_models[corner]['x_model']
        y_model = corner_models[corner]['y_model']
        print(f"Using specialized model for {corner}")
    else:
        x_model = general_models['x_model']
        y_model = general_models['y_model']
        print("Using general model")

    # Make predictions
    x_pred = int(x_model.predict([features])[0])
    y_pred = int(y_model.predict([features])[0])

    # Calculate confidence based on prediction variance
    x_preds = []
    y_preds = []

    # Get predictions from individual estimators for confidence estimation
    for x_estimator in x_model.estimators_:
        x_preds.append(x_estimator.predict([features])[0])

    for y_estimator in y_model.estimators_:
        y_preds.append(y_estimator.predict([features])[0])

    x_std = np.std(x_preds)
    y_std = np.std(y_preds)
    max_std = max(x_std, y_std)

    # Convert std dev to confidence (lower std dev = higher confidence)
    confidence = max(0, min(1, 1.0 - (max_std / 25.0)))

    print(f"GB detection: ({x_pred}, {y_pred}) with confidence {confidence:.2f}")

    # Visualization for debugging
    debug_img = corner_image.copy()
    cv2.circle(debug_img, (x_pred, y_pred), 5, (0, 255, 0), -1)

    # Create debug folder
    debug_folder = os.path.join(os.path.dirname(model_path), 'debug_predictions')
    os.makedirs(debug_folder, exist_ok=True)

    # Save debug image
    debug_name = f"{image_name}_{corner}_pred_gb.jpg" if image_name and corner else "prediction_gb.jpg"
    cv2.imwrite(os.path.join(debug_folder, debug_name), debug_img)

    return x_pred, y_pred, confidence
def extract_enhanced_features(image, size=(64, 64)):
    """
    Extract HOG features from image for better detection

    :param image: Input image
    :param size: Size to resize to
    :return: HOG feature vector
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Resize to fixed size
    resized = cv2.resize(gray, size)

    # Apply contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(resized)

    # Extract HOG features
    from skimage.feature import hog

    # HOG parameters
    orientations = 9
    pixels_per_cell = (8, 8)
    cells_per_block = (2, 2)

    hog_features = hog(
        enhanced,
        orientations=orientations,
        pixels_per_cell=pixels_per_cell,
        cells_per_block=cells_per_block,
        block_norm='L2-Hys',
        visualize=False
    )

    # Add pixel intensity features from key regions
    center_region = enhanced[size[0]//4:3*size[0]//4, size[1]//4:3*size[1]//4]
    intensity_features = center_region.flatten() / 255.0

    # Combine features
    combined_features = np.concatenate([hog_features, intensity_features])

    return combined_features


if __name__ == "__main__":
    # Manually set paths for testing
    mode = 'train'  # 'prepare' or 'train'
    fiducial_csv_path = r"D:\PROCESSING\SCANS\Manono_1952\PROCESSING\A_CanvasSized_Cropped\Out_fiducialmarks.csv"
    images_folder = r'D:\PROCESSING\SCANS\Manono_1952\PROCESSING\A_CanvasSized_Cropped'
    output_folder = r'D:\PROCESSING\SCANS\Manono_1952\PROCESSING\A_CanvasSized_Cropped\trained_model'

    # Create the folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    if mode == 'prepare':
        annotations_file = prepare_training_data_from_csv(fiducial_csv_path, images_folder, output_folder)
        print(f"Annotations saved to {annotations_file}")

    elif mode == 'train':
        annotations_file = os.path.join(output_folder, 'annotations.csv')
        if os.path.exists(annotations_file):
            # Train RF model
            print("Training Random Forest model...")
            rf_model_path = os.path.join(output_folder, 'fiducial_rf_model.joblib')
            train_fiducial_model(output_folder, annotations_file, rf_model_path, model='RF')

            # Train GB model
            print("\nTraining Gradient Boosting model...")
            gb_model_path = os.path.join(output_folder, 'fiducial_gb_model.joblib')
            train_fiducial_model(output_folder, annotations_file, gb_model_path, model='GB')
        else:
            print(f"Annotations file not found: {annotations_file}")