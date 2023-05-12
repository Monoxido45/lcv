import numpy as np
import pandas as pd
import os
from os import path

# base models and graph tools
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor

# conformal methods
from nonconformist.cp import IcpRegressor
from nonconformist.nc import NcFactory
from lcv.locart import LocalRegressionSplit, LocartSplit, MondrianRegressionSplit, QuantileSplit
from lcv.locart import LocartSplit, MondrianRegressionSplit
from lcv.locluster import KmeansSplit
from lcv.scores import RegressionScore, LocalRegressionScore

# importing LCP-RF
from acpi import ACPI

# performance measures
import time
from lcv.utils import compute_interval_length, split, smis, pearson_correlation, HSIC_correlation
from lcv.valid_pred_sets import Valid_pred_sets
import gc

# original path
original_path = os.getcwd()

# adapting code used in simulation data to real data
def compute_metrics(
  data_name,
  n_it = 100,
  completing = False,
  iter_completing = 50,
  base_model = RandomForestRegressor, 
  sig = 0.1,
  test_size = 0.2,
  is_fitted = True,
  valid_test_size = 0.3,
  valid_split = False,
  valid_min_sample = 150,
  save_all = True,
  valid_prune = True,
  calib_size = 0.5, 
  random_seed = 1250,
  random_projections = False,
  h = 20,
  m = 300,
  split_calib = False,
  nbins = 30,
  split_mondrian = False,
  criterion = "squared_error",
  max_depth = None,
  max_leaf_nodes = None,
  min_samples_leaf = 150,
  prune = True,
  **kwargs):
    # starting experiment
    print("Starting experiments for {} data".format(data_name))
    start_kind = time.time()
    
    # importing data into pandas data frame
    data_path = original_path + "/data/processed/" + data_name + ".csv"
    data = pd.read_csv(data_path)
    
    # separating y and X arrays
    y = data["target"].to_numpy()
    X = (data.
    drop("target", axis = 1).
    to_numpy())
    
    print("Number of samples that will be used for training and calibration: {}".format((1 - test_size)*X.shape[0]))
    print("Number of samples used for testing: {}".format(test_size*X.shape[0]))
    
    # managing directories
    folder_path = "/results/pickle_files/real_data_experiments/{}_data".format(
        data_name)
        
    # creating directories to each file
    if not(path.exists(original_path + folder_path)):
      os.mkdir(original_path + folder_path)
    
    # generating two random seeds vector
    np.random.seed(random_seed)
    random_seeds = np.random.randint(0, 10**(8), n_it)
    
    # testing wheter we already have all saved
    # if not, we run all and save all together in the same folder
    var_path = "/{}_data_score_regression_measures".format(data_name)
    if not(path.exists(original_path + folder_path + var_path)) or completing:
      if not completing:
        print("running the experiments for {} data".format(data_name))
        # measures to be saved at last
        # estimated measures
        smis_vector, pcor_vector, HSIC_vector = np.zeros((n_it, 9)), np.zeros((n_it, 9)), np.zeros((n_it, 9))
        mean_valid_pred_set, max_valid_pred_set = np.zeros((n_it, 9)), np.zeros((n_it, 9))
        mean_int_length_vector, mean_coverage_vector = np.zeros((n_it, 9)), np.zeros((n_it, 9))
        mean_int_length_cover_vector = np.zeros((n_it, 9))
      
        # running times
        times = np.zeros((n_it, 9))
        init_it = 0
      else:
        os.chdir(original_path + folder_path + var_path)
        print("continuing experiments for {} data".format(data_name))
        # measures to be saved at last
        # real measures
        mean_int_length_vector = np.load("mean_interval_length_{}_data.npy".format(
        data_name))
        
        mean_coverage_vector = np.load("mean_coverage_{}_data.npy".format(
        data_name))
        
        mean_valid_pred_set, max_valid_pred_set = (np.load("mean_valid_pred_set_{}_data.npy".format(
          data_name
        )), np.load("max_valid_pred_set_{}_data.npy".format(
          data_name
        )))
      
        # estimated measures
        smis_vector =  (np.load("smis_{}_data.npy".format(
        data_name)))
        
        pcor_vector, HSIC_vector = (np.load("pcor_{}_data",format(
          data_name)), np.load("HISC_{}_data").format(data_name))
          
        mean_int_length_cover_vector = np.load("mean_interval_length_cover_{}_data.npy".format(
          data_name))
      
        # running times
        times = np.load("run_times_{}_data.npy".format(
          data_name))
        init_it = iter_completing
        
      for it in range(init_it, n_it):
        if (it + 1) % 25 == 0:
          print("running {} iteration for {} data".format(it + 1, data_name))
        seed = random_seeds[it]
        
        # splitting data into train, test and calibration sets
        data = split(X, y, test_size = test_size, calib_size = calib_size, calibrate = True, random_seed = seed)
        X_test, y_test = data["X_test"], data["y_test"]
        
        # fitting base model
        model = base_model(**kwargs).fit(data["X_train"], data["y_train"])
        
        # fitting all methods, saving running times and each metric
        # fitting normal locart
        start_loc = time.time()
        locart_obj = LocartSplit(nc_score = RegressionScore, cart_type = "CART", 
        base_model = model, is_fitted = is_fitted, alpha = sig, split_calib = split_calib, **kwargs)
        locart_obj.fit(data["X_train"], data["y_train"])
        locart_obj.calib(data["X_calib"], data["y_calib"], max_depth = max_depth, 
        max_leaf_nodes = max_leaf_nodes, min_samples_leaf = min_samples_leaf, 
        criterion = criterion, prune_tree = prune, 
        random_projections = random_projections, m = m, h = h)
        
        end_loc = time.time() - start_loc
        times[it, 0] = end_loc
        
        # predictions
        locart_pred = np.array(locart_obj.predict(X_test))
        
         # valid pred sets
        locart_valid = Valid_pred_sets(conf = locart_obj, alpha = sig, 
        coverage_evaluator = "CART", prune = valid_prune, split_train = valid_split)
        locart_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 0], max_valid_pred_set[it, 0] = locart_valid.compute_dif()
          
        
        # marginal coverage
        marg_cover = np.logical_and(y_test >= locart_pred[:, 0], 
            y_test <= locart_pred[:, 1]) + 0
        mean_coverage_vector[it, 0] = np.mean(
            marg_cover
        )
    
        # smis
        smis_vector[it, 0] = smis(locart_pred, y_test, alpha = sig)
    
        # mean interval length
        mean_int_length_vector[it, 0] = np.mean(compute_interval_length(locart_pred))
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 0] = np.mean(compute_interval_length(locart_pred[cover_idx]))
        
        
        # correlations
        pcor_vector[it, 0] = pearson_correlation(locart_pred, y_test)
        HSIC_vector[it, 0] = HSIC_correlation(locart_pred, y_test)
        
        # deletting objects and removing from memory
        del(locart_obj)
        del(locart_valid)
        del(cover_idx)
        gc.collect()
    
        # fitting normal RF-locart
        start_loc = time.time()
        rf_locart_obj = LocartSplit(nc_score = RegressionScore, cart_type = "RF", base_model = model,
        is_fitted = is_fitted,alpha = sig, split_calib = split_calib, **kwargs)
        rf_locart_obj.fit(data["X_train"], data["y_train"])
        rf_locart_obj.calib(data["X_calib"], data["y_calib"], max_depth = max_depth, 
        max_leaf_nodes = max_leaf_nodes, min_samples_leaf = min_samples_leaf, criterion = criterion, 
        prune_tree = prune, random_projections = random_projections, 
        m = m, h = h)
        
        end_loc = time.time() - start_loc
        times[it, 1] = end_loc
        
        # predictions
        rf_locart_pred = np.array(rf_locart_obj.predict(X_test))
    
        # valid pred sets
        rf_locart_valid = Valid_pred_sets(conf = rf_locart_obj, alpha = sig, coverage_evaluator = "CART", 
        prune = valid_prune, split_train = valid_split)
        rf_locart_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 1], max_valid_pred_set[it, 1] = rf_locart_valid.compute_dif()
    
        # smis
        smis_vector[it, 1] = smis(rf_locart_pred, y_test, alpha = sig)
        
        #  correlations
        pcor_vector[it, 1] = pearson_correlation(rf_locart_pred, y_test)
        HSIC_vector[it, 1] = HSIC_correlation(rf_locart_pred, y_test)
    
        # mean interval length
        mean_int_length_vector[it, 1] = np.mean(compute_interval_length(rf_locart_pred))
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= rf_locart_pred[:, 0], 
            y_test <= rf_locart_pred[:, 1]) + 0
        mean_coverage_vector[it, 1] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 1] = np.mean(compute_interval_length(rf_locart_pred[cover_idx]))
    
    
        # fitting normal difficulty locart
        start_loc = time.time()
        dlocart_obj = LocartSplit(nc_score = RegressionScore, cart_type = "CART", 
        base_model = model, is_fitted = is_fitted, 
        alpha = sig, split_calib = split_calib, weighting = True,**kwargs)
        dlocart_obj.fit(data["X_train"], data["y_train"])
        dlocart_obj.calib(data["X_calib"], data["y_calib"], max_depth = max_depth, 
        max_leaf_nodes = max_leaf_nodes, min_samples_leaf = min_samples_leaf, criterion = criterion, 
        prune_tree = prune, random_projections = random_projections, 
        m = m, h = h)
        
        end_loc = time.time() - start_loc
        times[it, 2] = end_loc
    
        # predictions
        dlocart_pred = np.array(dlocart_obj.predict(X_test))
    
        # valid pred sets
        dlocart_valid = Valid_pred_sets(conf = dlocart_obj, alpha = sig, coverage_evaluator = "CART", 
        prune = valid_prune, split_train = valid_split)
        dlocart_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 2], max_valid_pred_set[it, 2] = dlocart_valid.compute_dif()
    
        # smis
        smis_vector[it, 2] = smis(dlocart_pred, y_test, alpha = sig)
        
        
        pcor_vector[it, 2] = pearson_correlation(dlocart_pred, y_test)
        HSIC_vector[it, 2] = HSIC_correlation(dlocart_pred, y_test)
    
        # mean interval length
        mean_int_length_vector[it, 2]  = np.mean(compute_interval_length(dlocart_pred))
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= dlocart_pred[:, 0], 
            y_test <= dlocart_pred[:, 1]) + 0
        mean_coverage_vector[it, 2] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 2] = np.mean(compute_interval_length(dlocart_pred[cover_idx]))
    
    
        # fitting RF difficulty locart
        start_loc = time.time()
        rf_dlocart_obj = LocartSplit(nc_score = RegressionScore, cart_type = "RF", base_model = model,
        is_fitted = is_fitted, alpha = sig, split_calib = split_calib, weighting = True, **kwargs)
        rf_dlocart_obj.fit(data["X_train"], data["y_train"])
        rf_dlocart_obj.calib(data["X_calib"], data["y_calib"], max_depth = max_depth, 
        max_leaf_nodes = max_leaf_nodes, min_samples_leaf = min_samples_leaf, criterion = criterion, 
        prune_tree = prune, random_projections = random_projections, 
        m = m, h = h)
        
        end_loc = time.time() - start_loc
        times[it, 3] = end_loc
    
        # predictions
        rf_dlocart_pred = np.array(rf_dlocart_obj.predict(X_test))
    
        # valid pred sets
        rf_dlocart_valid = Valid_pred_sets(conf = rf_dlocart_obj, alpha = sig, coverage_evaluator = "CART", 
        prune = valid_prune, split_train = valid_split)
        rf_dlocart_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 3], max_valid_pred_set[it, 3] = rf_dlocart_valid.compute_dif()
    
        # smis
        smis_vector[it, 3] = smis(rf_dlocart_pred, y_test, alpha = sig)
    
        # mean interval length
        mean_int_length_vector[it, 3] = np.mean(compute_interval_length(rf_dlocart_pred))
        
        pcor_vector[it, 3] = pearson_correlation(rf_dlocart_pred, y_test)
        HSIC_vector[it, 3] = HSIC_correlation(rf_dlocart_pred, y_test)
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= rf_dlocart_pred[:, 0], 
            y_test <= rf_dlocart_pred[:, 1]) + 0
        mean_coverage_vector[it, 3] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 3] = np.mean(compute_interval_length(rf_dlocart_pred[cover_idx]))

    
        # fitting ACPI/LCP-RF
        start_loc = time.time()
        acpi = ACPI(model_cali = model, n_estimators = 100)
        acpi.fit(data["X_calib"], data["y_calib"], nonconformity_func = None)
        acpi.fit_calibration(data["X_calib"], data["y_calib"], quantile = 1 - sig, only_qrf = True)
    
        end_loc = time.time() - start_loc
        times[it, 4] = end_loc
        
        acpi_pred = np.stack((acpi.predict_pi(X_test, method = "qrf")), axis = -1)
    
        # valid pred sets
        acpi_valid = Valid_pred_sets(conf = acpi, alpha = sig, islcp = True, coverage_evaluator = "CART", 
        prune = valid_prune, split_train = valid_split)
        acpi_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 4], max_valid_pred_set[it, 4] = acpi_valid.compute_dif()
    
        # smis
        smis_vector[it, 4] = smis(acpi_pred, y_test, alpha = sig)
        
        pcor_vector[it, 4] = pearson_correlation(acpi_pred, y_test)
        HSIC_vector[it, 4] = HSIC_correlation(acpi_pred, y_test)
    
        # mean interval length
        mean_int_length_vector[it, 4] = np.mean(compute_interval_length(acpi_pred))
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= acpi_pred[:, 0], 
            y_test <= acpi_pred[:, 1]) + 0
        mean_coverage_vector[it, 4] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 4] = np.mean(compute_interval_length(acpi_pred[cover_idx]))
        
    
        # fitting wlocart
        start_loc = time.time()
    
        wlocart_obj = LocartSplit(nc_score = LocalRegressionScore, cart_type = "RF", base_model = model,
        is_fitted = is_fitted, alpha = sig, split_calib = split_calib, **kwargs)
        wlocart_obj.fit(data["X_train"], data["y_train"])
        wlocart_obj.calib(data["X_calib"], data["y_calib"], max_depth = max_depth, 
            max_leaf_nodes = max_leaf_nodes, min_samples_leaf = min_samples_leaf, criterion = criterion, 
            prune_tree = prune, random_projections = random_projections, m = m, h = h)
        
        end_loc = time.time() - start_loc
        times[it, 5] = end_loc
    
        # predictions
        wlocart_pred = np.array(wlocart_obj.predict(X_test))
    
        # valid pred sets
        wlocart_valid = Valid_pred_sets(conf = wlocart_obj, alpha = sig, coverage_evaluator = "CART", 
        prune = valid_prune, split_train = valid_split)
        wlocart_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 5], max_valid_pred_set[it, 5] = wlocart_valid.compute_dif()
    
        # smis
        smis_vector[it, 5] = smis(wlocart_pred, y_test, alpha = sig)
        
        pcor_vector[it, 5] = pearson_correlation(wlocart_pred, y_test)
        HSIC_vector[it, 5] = HSIC_correlation(wlocart_pred, y_test)
    
        # mean interval length
        mean_int_length_vector[it, 5] = np.mean(compute_interval_length(wlocart_pred))
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= wlocart_pred[:, 0], 
            y_test <= wlocart_pred[:, 1]) + 0
        mean_coverage_vector[it, 5] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 5] = np.mean(compute_interval_length(wlocart_pred[cover_idx]))
    
    
        # fitting default regression split
        start_split = time.time()
        model = base_model(**kwargs)
        nc = NcFactory.create_nc(model)
        icp = IcpRegressor(nc)
        icp.fit(data["X_train"], data["y_train"])
        icp.calibrate(data["X_calib"], data["y_calib"])
    
        end_split = time.time() - start_split
        times[it, 6] = end_split

        # predictions
        icp_pred = icp.predict(X_test, significance = sig)
    
        # valid pred sets
        icp_valid = Valid_pred_sets(conf = icp, alpha = sig, isnc = True, coverage_evaluator = "CART", 
        prune = valid_prune, split_train = valid_split)
        icp_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 6], max_valid_pred_set[it, 6] = icp_valid.compute_dif()
    
        # icp smis
        smis_vector[it, 6] = smis(icp_pred, y_test, alpha = sig)
        
        pcor_vector[it, 6] = pearson_correlation(icp_pred, y_test)
        HSIC_vector[it, 6] = HSIC_correlation(icp_pred, y_test)
    
        # ICP interval length
        mean_int_length_vector[it, 6] = np.mean(compute_interval_length(icp_pred))
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= icp_pred[:, 0], 
            y_test <= icp_pred[:, 1]) + 0
        mean_coverage_vector[it, 6] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 6] = np.mean(compute_interval_length(icp_pred[cover_idx]))
    
        # fitting wighted regression split
        start_weighted_split = time.time()
        wicp = LocalRegressionSplit(model, is_fitted = True, alpha = sig, **kwargs)
        wicp.fit(data["X_train"], data["y_train"])
        wicp.calibrate(data["X_calib"], data["y_calib"])
    
        end_weighted_split = time.time() - start_weighted_split
        times[it, 7] = end_weighted_split
    
        # predictions
        wicp_pred = wicp.predict(X_test)
    
        # valid pred sets
        wicp_valid = Valid_pred_sets(conf = wicp, alpha = sig, coverage_evaluator = "CART", prune = valid_prune, 
        split_train = valid_split)
        wicp_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 7], max_valid_pred_set[it, 7] = wicp_valid.compute_dif()
    
        # smis
        smis_vector[it, 7] = smis(wicp_pred, y_test, alpha = sig)
        
        pcor_vector[it, 7] = pearson_correlation(wicp_pred, y_test)
        HSIC_vector[it, 7] = HSIC_correlation(wicp_pred, y_test)
    
        # ICP interval length
        mean_int_length_vector[it, 7] = np.mean(compute_interval_length(wicp_pred))
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= wicp_pred[:, 0], 
            y_test <= wicp_pred[:, 1]) + 0
        mean_coverage_vector[it, 7] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 7] = np.mean(compute_interval_length(wicp_pred[cover_idx]))

        start_weighted_split = time.time()
        micp = MondrianRegressionSplit(model, is_fitted = is_fitted, alpha = sig, k = nbins, **kwargs)
        micp.fit(data["X_train"], data["y_train"])
        micp.calibrate(data["X_calib"], data["y_calib"], split = split_mondrian)
    
        end_weighted_split = time.time() - start_weighted_split
        times[it, 8] = end_weighted_split
    
        # predictions
        micp_pred = micp.predict(X_test)
    
        # valid pred sets
        micp_valid = Valid_pred_sets(conf = micp, alpha = sig, coverage_evaluator = "CART", prune = valid_prune, 
        split_train = valid_split)
        micp_valid.fit(X_test, y_test, test_size = valid_test_size, min_samples_leaf = valid_min_sample)
        mean_valid_pred_set[it, 8], max_valid_pred_set[it, 8] = micp_valid.compute_dif()
    
        # smis
        smis_vector[it, 8] = smis(micp_pred, y_test, alpha = sig)
        
        pcor_vector[it, 8] = pearson_correlation(micp_pred, y_test)
        HSIC_vector[it, 8] = HSIC_correlation(micp_pred, y_test)
    
        # ICP interval length
        mean_int_length_vector[it, 8] = np.mean(compute_interval_length(micp_pred))
    
        # marginal coverage
        marg_cover = np.logical_and(y_test >= micp_pred[:, 0], 
            y_test <= micp_pred[:, 1]) + 0
        mean_coverage_vector[it, 8] = np.mean(
            marg_cover
        )
        
        # interval length | coveraqe
        cover_idx = np.where(marg_cover == 1)
        mean_int_length_cover_vector[it, 8] = np.mean(compute_interval_length(micp_pred[cover_idx]))
        
        if (it + 1) % 25 == 0 or (it + 1 == 1) or save_all:
          print("Saving data checkpoint on iteration {}".format(it + 1))
          # saving checkpoint of metrics
          saving_metrics(original_path, folder_path, var_path, data_name,
          mean_int_length_vector, mean_int_length_cover_vector,
          mean_coverage_vector, smis_vector, mean_valid_pred_set,
          max_valid_pred_set, pcor_vector, HSIC_vector, times)
    
        # saving all metrics again
        saving_metrics(original_path, folder_path, var_path, data_name,
        mean_int_length_vector, mean_int_length_cover_vector,
        mean_coverage_vector, smis_vector, mean_valid_pred_set,
        max_valid_pred_set, pcor_vector, HSIC_vector, times)
      
    print("Experiments finished for {} data".format(data_name))
    end_kind = time.time() - start_kind
    print("Time Elapsed to compute all metrics in the {} data: {}".format(data_name, end_kind))
    return end_kind

# saving metrics function
def saving_metrics(
  original_path, 
  folder_path, 
  var_path,
  data_name,
  mean_int_length_vector,
  mean_int_length_cover_vector,
  mean_coverage_vector,
  smis_vector,
  mean_valid_pred_set,
  max_valid_pred_set,
  pcor_vector, 
  HSIC_vector,
  times):
    # checking if path exsist
    if not(path.exists(original_path + folder_path + var_path)):
      # creating directory
      os.mkdir(original_path + folder_path + var_path)
 
    # changing working directory to the current folder
    os.chdir(original_path + folder_path + var_path)
      
    # saving all matrices into npy files
    # interval length
    np.save("mean_interval_length_{}_data.npy".format(
      data_name), mean_int_length_vector)
      
    np.save("mean_interval_length_cover_{}_data.npy".format(
      data_name), mean_int_length_cover_vector)
      
    # mean coverage
    np.save("mean_coverage_{}_data.npy".format(
      data_name), mean_coverage_vector)
      
    # estimated metrics
    np.save("smis_{}_data.npy".format(
      data_name), smis_vector)
      
    np.save("mean_valid_pred_set_{}_data.npy".format(
      data_name), mean_valid_pred_set)
    np.save("max_valid_pred_set_{}_data.npy".format(
      data_name), max_valid_pred_set)
      
    np.save("pcor_{}_data.npy".format(
      data_name), pcor_vector)
    np.save("HSIC_{}_data.npy".format(
      data_name), HSIC_vector)
      
    # running times
    np.save("run_times_{}_data.npy".format(
      data_name), times)
    
    # returning to original path
    os.chdir(original_path)

if __name__ == '__main__':
  print("We will now compute all conformal statistics for real data")
  model = input("Which model would like to use as base model? ")
  data_name = input("Which data would you like to use? ")
  if model == "Random Forest":
    random_state = 650
    
    print("Starting real data experiment")
    exp_time = compute_metrics(data_name = data_name, base_model = RandomForestRegressor, random_state = random_state)
    print("Time elapsed to conduct all experiments: {}".format(exp_time))
    
    np.save("results/pickle_files/real_data_experiments/{}_running_time.npy".format(data_name), 
    np.array([exp_time]))

  elif model == "KNN":
    print("Starting real data experiment")
    exp_time = compute_metrics(data_name = data_name, base_model = KNeighborsRegressor, n_neighbors = 30)
    print("Time elapsed to conduct all experiments: {}".format(exp_time))
    
    np.save("results/pickle_files/real_data_experiments/{}_running_time.npy".format(data_name), 
    np.array([exp_time]))



