import numpy as np
import pandas as pd

# Handle RDKit imports with better error handling and version compatibility
try:
    from rdkit import Chem
    from rdkit.Chem import MACCSkeys, Descriptors
    
    # Dynamic imports to avoid type checker issues
    rdFingerprintGenerator = None
    rdMolDescriptors = None
    HAS_NEW_FP_GENERATOR = False
    
    # Try to import the new fingerprint generator (RDKit 2021.03+)
    try:
        import importlib
        rdFingerprintGenerator = importlib.import_module('rdkit.Chem.rdFingerprintGenerator')
        HAS_NEW_FP_GENERATOR = True
    except ImportError:
        # Fall back to older imports for older RDKit versions
        try:
            rdMolDescriptors = importlib.import_module('rdkit.Chem.rdMolDescriptors')
            HAS_NEW_FP_GENERATOR = False
        except ImportError:
            pass
        
    RDKIT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: RDKit not available: {e}")
    print("Please install RDKit: conda install -c conda-forge rdkit")
    RDKIT_AVAILABLE = False
    rdFingerprintGenerator = None
    rdMolDescriptors = None
    HAS_NEW_FP_GENERATOR = False

def _convert_numpy_types(value):
    """
    Convert NumPy scalar types to native Python types for cleaner output.
    
    Parameters:
        value: Input value, possibly a NumPy scalar
    
    Returns:
        Native Python type (int, float, etc.) or original value if not a NumPy type
    """
    if isinstance(value, np.floating):
        return float(value)
    elif isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.bool_):
        return bool(value)
    return value

def calculate_molecular_features(smiles, fp_type=None, descriptors=False, radius=2, nBits=2048):
    """
    Calculate molecular fingerprints and/or all RDKit descriptors for a single SMILES string,
    returning a columnar DataFrame suitable for CSV export.
    
    Parameters:
        smiles (str): A single SMILES string
        fp_type (str or None): Fingerprint type, must be "maccs", "morgan", "rdkit", "atompair", "torsion", or None
        descriptors (str or bool): Descriptor mode: "all" (all RDKit descriptors) or False (no descriptors)
        radius (int): Radius for Morgan fingerprint (default: 2)
        nBits (int): Number of bits for Morgan, RDKit, AtomPair, and Torsion fingerprints (default: 2048)
    
    Returns:
        pandas.DataFrame: DataFrame with SMILES as index and columns for fingerprints/descriptors,
                          or None if SMILES is invalid
    """

    # Check if RDKit is available
    if not RDKIT_AVAILABLE:
        print("Error: RDKit is not available. Cannot calculate molecular features.")
        return None
    
    # Validate input
    if not isinstance(smiles, str):
        raise ValueError("Input must be a single SMILES string")
    
    # Validate fp_type and descriptors
    valid_fp_types = [None, "maccs", "morgan", "rdkit", "atompair", "torsion"]
    if fp_type not in valid_fp_types:
        raise ValueError(f"Fingerprint type must be one of {valid_fp_types}")
    if descriptors not in [False, "all"]:
        raise ValueError("Descriptors must be 'all' or False")
    
    # Get all RDKit descriptors from _descList
    descriptor_funcs = None
    if descriptors == "all":
        try:
            descriptor_funcs = {name: func for name, func in Descriptors._descList}
        except AttributeError:
            print("Warning: Could not access RDKit descriptors list")
            descriptor_funcs = None
    
    # Convert SMILES to molecule
    mol = Chem.MolFromSmiles(smiles)  # type: ignore
    if mol is None:
        print(f"Invalid SMILES: {smiles}")
        return None
    
    # Initialize row data
    row = {}
    
    # Calculate fingerprint if requested
    if fp_type is not None:
        if fp_type.lower() == "maccs":
            fp = MACCSkeys.GenMACCSKeys(mol)  # type: ignore
            fp_array = np.array(fp)
            prefix = "maccs"
        elif fp_type.lower() == "morgan" and rdFingerprintGenerator is not None:
            morgan_gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=nBits)
            fp = morgan_gen.GetFingerprint(mol)
            fp_array = np.array(fp)
            prefix = "morgan"
        elif fp_type.lower() == "rdkit" and rdFingerprintGenerator is not None:
            rdk_gen = rdFingerprintGenerator.GetRDKitFPGenerator(maxPath=7, fpSize=nBits)
            fp = rdk_gen.GetFingerprint(mol)
            fp_array = np.array(fp)
            prefix = "rdkit"
        elif fp_type.lower() == "atompair" and rdFingerprintGenerator is not None:
            ap_gen = rdFingerprintGenerator.GetAtomPairGenerator(fpSize=nBits)
            fp = ap_gen.GetFingerprint(mol)
            fp_array = np.array(fp)
            prefix = "atompair"
        elif fp_type.lower() == "torsion" and rdFingerprintGenerator is not None:
            torsion_gen = rdFingerprintGenerator.GetTopologicalTorsionGenerator(fpSize=nBits)
            fp = torsion_gen.GetFingerprint(mol)
            fp_array = np.array(fp)
            prefix = "torsion"
        else:
            print(f"Warning: Fingerprint type '{fp_type}' not available or rdFingerprintGenerator not loaded")
            return None
        
        # Add fingerprint bits as columns
        for i in range(len(fp_array)):
            row[f"{prefix}_{i+1}"] = int(fp_array[i])
    
    # Calculate descriptors if requested
    if descriptors == "all" and descriptor_funcs is not None:
        for name, func in descriptor_funcs.items():
            try:
                value = _convert_numpy_types(func(mol))
                row[name] = value if value is not None else 0.0
            except Exception as e:
                print(f"Error computing descriptor {name} for {smiles}: {str(e)}")
                row[name] = 0.0
    
    # Create DataFrame with SMILES as index
    df = pd.DataFrame([row], index=[smiles])
    
    return df

# Example usage with your input
if __name__ == "__main__":
    # Your input
    smiles = "c1ccccc1"
    feature_type = {"fp_type": "maccs", "descriptors": "all"}
    
    fp_type = feature_type["fp_type"]
    descriptors = feature_type["descriptors"]
    
    # Calculate features
    df = calculate_molecular_features(smiles, fp_type=fp_type, descriptors=descriptors, radius=2, nBits=2048)  # type: ignore
    
    if df is not None:
        print(f"\nGenerated DataFrame (MACCS + Descriptors):")
        print(df.iloc[:, :10], "...")  # Show first 10 columns for brevity
        
        # Export to CSV
        csv_path = "molecule_features_maccs.csv"
        df.to_csv(csv_path)
        print(f"\nCSV exported to: {csv_path}")
        
        # Downstream calculation
        print(f"\nDownstream Calculation for {smiles}:")
        vector = df.iloc[0].values
        print(f"Vector Sum: {np.sum(vector):.4f}")
        print(f"Vector Mean: {np.mean(vector):.4f}")
        print(f"Non-zero elements: {np.sum(vector != 0)}")
    
    # Test with all fingerprint types
    for fp_type in ["morgan", "rdkit", "atompair", "torsion"]:
        print(f"\nTesting with {fp_type} fingerprint only:")
        df = calculate_molecular_features(smiles, fp_type=fp_type, descriptors=False, radius=2, nBits=2048)
        
        if df is not None:
            print(f"\nGenerated DataFrame ({fp_type} Fingerprint Only):")
            print(df.iloc[:, :10], "...")  # Show first 10 columns
            csv_path = f"molecule_features_{fp_type}.csv"
            df.to_csv(csv_path)
            print(f"\nCSV exported to: {csv_path}")
            
            print(f"\nDownstream Calculation for {smiles} ({fp_type} Fingerprint):")
            vector = df.iloc[0].values
            print(f"Vector Sum: {np.sum(vector):.4f}")
            print(f"Vector Mean: {np.mean(vector):.4f}")
            print(f"Non-zero elements: {np.sum(vector != 0)}")
    
    # Test with descriptors only
    print("\nTesting with descriptors only:")
    df = calculate_molecular_features(smiles, fp_type=None, descriptors="all")  # type: ignore
    
    if df is not None:
        print("\nGenerated DataFrame (Descriptors Only):")
        print(df.iloc[:, :10], "...")
        csv_path = "molecule_descriptors_only.csv"
        df.to_csv(csv_path)
        print(f"\nCSV exported to: {csv_path}")
        
        print(f"\nDownstream Calculation for {smiles} (Descriptors Only):")
        vector = df.iloc[0].values
        print(f"Vector Sum: {np.sum(vector):.4f}")
        print(f"Vector Mean: {np.mean(vector):.4f}")
        print(f"Non-zero elements: {np.sum(vector != 0)}")