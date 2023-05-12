# formatting raw data into new csv file
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from os import path
import pandas as pd
from pandas.api.types import CategoricalDtype

# 9 columns in raw data
# first column is normal locart
# second column is random forest locart
# third is difficulty locart
# forth is difficulty random forest locart
# fifth is LCP-RF
# sixth is weighted locart
# seventh is ICP
# eighth is WICP
# and nineth is mondrian split

original_path = os.getcwd()
# plotting object (if needed)
plt.style.use('seaborn-white')
sns.set_palette("tab10")
plt.rcParams.update({'font.size': 12})

# creating csv file with all needed data
def create_data_list(kind, 
p = np.array([1, 3, 5]),
n_it = 100,
exp_path = "/results/pickle_files/locart_all_metrics_experiments/",
other_asym = False):
  
  # folder path
  folder_path = exp_path + kind + "_data"
  print(folder_path)
  if other_asym:
    folder_path = folder_path + "_eta_1.5"
  
  # strings names to be used
  max_diff, mean_diff, median_diff = "max_diff", "mean_diff", "median_diff"
  mean_int, mean_coverage = "mean_interval_length", "mean_coverage"
  mean_valid, max_valid = "mean_valid_pred_set", "max_valid_pred_set"
  hsic, pcor, smis, wsc = "HSIC", "pcor", "smis", "wsc"
  
  # name of each method
  methods = ["locart", "RF-locart", "Dlocart", "RF-Dlocart", "LCP-RF", "Wlocart", "icp", "wicp", "mondrian"]
  
  string_names = [mean_diff, median_diff, max_diff, smis, wsc, hsic, pcor, mean_valid, max_valid, mean_int, mean_coverage]
  
  # checking if path exists and then importing all data matrices
  if path.exists(original_path + folder_path):
    print("Creating data list")
    # list of data frames
    stat_list = list()
    corr_list = list()
    for i in range(p.shape[0]):
      # importing the data
      current_folder = original_path + folder_path + "/{}_score_regression_p_{}_10000_samples_measures".format(
        kind, p[i])
      
      # looping through all string names
      data_list = []
      corr_data_list = []
      for string in string_names:
        current_data = np.load(current_folder + "/" + string + "_p_{}_{}_data.npy".format(p[i], kind))
        # removing rows with only zeroes
        current_data = current_data[~np.all(current_data == 0, axis = 1)]
        if string == "smis":
          current_data = - current_data
        # data list for extracting means  
        data_list.append(current_data)
        # transforming in pandas data frame and making a list of data frames to plot correlation more latter
        corr_data = (pd.DataFrame(current_data, columns = methods).
        assign(p_var = p[i], 
               metric = string).
        melt(id_vars = ["p_var", "metric"],
        value_vars = methods,
        var_name = "methods"))
        corr_data_list.append(corr_data)
      
      # adding to correlation data list
      corr_list.append(pd.concat(corr_data_list))
      
      # obtaining mean vectors in each matrix
      means_list = [np.mean(data, axis = 0) for data in data_list]
      # standard deviation
      sd_list = [np.std(data, axis = 0) for data in data_list]
      
      # transforming means_list and sd_list into a matrix
      means_array = np.column_stack(means_list)
      
      # transforming sd into a flat array
      sd_array = np.concatenate(sd_list)
      
      # transforming into a pandas dataframe and adding a new variable identifying the n and the methods
      # and melting it to add varible column
      new_data = (pd.DataFrame(means_array,
      columns = string_names).
      assign(p_var = p[i],
      methods = methods).
      melt(id_vars = ["p_var", "methods"],
      value_vars = string_names,
      var_name = "stats").
      assign(sd = sd_array/np.sqrt(n_it)))
      
      
      # adding to a list of data frames
      stat_list.append(new_data)
      
    # concatenating the data frames list into a single one data and saving it to csv
    data_final = pd.concat(stat_list)
    # saving to csv and returning
    data_final.to_csv(original_path + folder_path + "/{}_stats.csv".format(kind))
    
    # doing the same to correlation data
    data_corr_final = pd.concat(corr_list)
    data_corr_final.to_csv(original_path + folder_path + "/{}_corr_data.csv".format(kind))
    return(data_final)


def create_data_times(kind, 
p = np.array([1, 3, 5]),
exp_path = "/results/pickle_files/locart_all_metrics_experiments/",
other_asym = False):
    # folder path
  folder_path = exp_path + kind + "_data"
  print(folder_path)
  if other_asym:
    folder_path = folder_path + "_eta_1.5"
  
  string = "run_times"
  
  # name of each method
  methods = ["locart", "RF-locart", "Dlocart", "RF-Dlocart", "LCP-RF", "Wlocart", "icp", "wicp", "mondrian"]
  
  # checking if path exists and then importing all data matrices
  if path.exists(original_path + folder_path):
    print("Creating data list")
    # list of data frames
    data_list = list()
    times_list = list()
    for i in range(p.shape[0]):
      # importing the data
      current_folder = original_path + folder_path + "/{}_score_regression_p_{}_10000_samples_measures".format(
        kind, p[i])
        
      # only one string name
      current_data = np.load(current_folder + "/" + string + "_p_{}_{}_data.npy".format(p[i], kind))
      # removing rows with only zeroes
      current_data = current_data[~np.all(current_data == 0, axis = 1)]
      
      new_data = (pd.DataFrame(current_data,
      columns = methods).
      assign(p_var = p[i]).
      melt(id_vars = ["p_var"],
      value_vars = methods,
      var_name = "methods"))
      
       # obtaining proportions by row
      prop_data = current_data/np.sum(current_data, axis = 1)[:, None]
    
      # proportion data
      data_prop = (pd.DataFrame(prop_data,
      columns = methods).
      assign(p_var = p[i]).
      melt(
        id_vars = ["p_var"],
        value_vars = methods,
        var_name = "methods"
      ))
      
      # adding to a list of data frames
      data_list.append(new_data)
      times_list.append(data_prop)
      
    # concatenating the data frames list into a single one data and saving it to csv
    data_final = pd.concat(data_list)
    time_data = pd.concat(times_list)
    
    # saving to csv and returning
    data_final.to_csv(original_path + folder_path + "/{}_running_times.csv".format(kind))
    time_data.to_csv(original_path + folder_path + "/{}_prop_times.csv".format(kind))
    return(data_final)


# creating data_list to several kind of data
def create_all_data(kind_list = ["homoscedastic", "heteroscedastic", "asymmetric", 
"asymmetric_V2", "t_residuals", "non_cor_heteroscedastic"],
p = np.array([1,3,5]),
n_it = 100,
times = False):
  data_list = []
  for kind in kind_list:
    if kind == "asymmetric_V2":
      other_asym = True
      kind = "asymmetric"
    else:
      other_asym = False
      
    if times:
      # assigning type of data
      data = (create_data_times(kind, p = p, other_asym = other_asym).
      assign(data_type = kind))
      
    else:
      # assigning the type of data
      data = (create_data_list(kind, p = p, n_it = n_it, other_asym = other_asym).
      assign(data_type = kind))
      
    data_list.append(data)
  return data_list


# saving several data at the same time and generating a list of data
data_list = create_all_data(p = np.array([1, 3, 5]))
data_time = create_all_data(p = np.array([1, 3, 5]), times = True)

def plot_results_by_methods(kind, 
p = np.array([1,3,5]),
images_dir = "results/metric_figures",
vars_to_plot = np.array(["mean_diff", "smis", "wsc", "mean_valid_pred_set"]),
vars_corr = np.array(["smis", "mean_valid_pred_set", "wsc", "pcor", "HSIC", "mean_diff", "max_diff"]),
other_vars = np.array(["mean_coverage", "mean_interval_length"]),
exp_path = "/results/pickle_files/locart_all_metrics_experiments/",
other_asym = False):
  if other_asym:
    figname = "performance/sim_{}_data_eta_1.5_regression_experiments".format(kind)
    fig_times = "times/sim_{}_data_eta_1.5_running_times".format(kind)
    fig_corr = "correlations/sim_{}_data_eta_1.5_corr_mat".format(kind)
    figname_others = "performance_other/sim_{}_data_eta_1.5_other_measures".format(kind)
    figname_p = "performance_vs_p/sim_{}_data_eta_1.5_regression_experiments".format(kind)
    folder_path = exp_path + kind + "_data_eta_1.5"
    kind_to_plot = "asymmetric_V2"
  else:
    figname = "performance/sim_{}_data_regression_experiments".format(kind)
    fig_times = "times/sim_{}_data_running_times".format(kind)
    fig_corr = "correlations/sim_{}_data_corr_mat".format(kind)
    figname_others = "performance_other/sim_{}_data_other_measures".format(kind)
    figname_p = "performance_vs_p/sim_{}_data_regression_experiments".format(kind)
    folder_path = exp_path + kind + "_data"
    kind_to_plot = kind
    
   # first creating the data list to be plotted
  data_main = (pd.read_csv(original_path + folder_path + "/{}_stats.csv".format(kind)).
  assign(sd = lambda df: df['sd']*2).
  query("p_var in @p"))
  
  # ordering data by custom order
  method_custom_order = CategoricalDtype(
    ["locart", "Dlocart", "RF-locart", "RF-Dlocart", "Wlocart", "LCP-RF", "icp", "wicp", "mondrian"], 
    ordered=True)
  
  # sorting according to the custom order
  data_main['methods'] = data_main['methods'].astype(method_custom_order)
  data_main = data_main.sort_values('methods')
  
  # with the final data in hands, we can plot the line plots as desired
  # faceting all in a seaborn plot
  g = sns.FacetGrid(data_main.
  query("stats in @vars_to_plot"), col = "stats", row = "p_var", hue = "methods",
  despine = False, margin_titles = True, legend_out = True,
  sharey = False,
  height = 5)
  g.map(plt.errorbar, "methods", "value", "sd", marker = "o")
  g.figure.subplots_adjust(wspace=0, hspace=0)
  g.add_legend(bbox_to_anchor = (1.0575, 0.5), title = "Methods")
  g.set_ylabels("Metric values")
  g.set_xlabels("Methods")
  g.set_xticklabels(rotation = 45)
  g.set_titles(col_template="{col_name}", row_template = "p = {row_name}")
  plt.tight_layout()
  plt.savefig(f"{images_dir}/{figname}.pdf", bbox_inches="tight")
  
  # importing running times data
  data_times = (pd.read_csv(original_path + folder_path + "/{}_running_times.csv".format(kind)).
  query("p_var in @p"))
  data_times['methods'] = data_times['methods'].astype(method_custom_order)
  data_times = data_times.sort_values('methods')
  
  # plotting running times as boxplot
  plt.figure(figsize = (16, 8))
  sns.boxplot(data = data_times, x = 'methods', y = 'value', hue = 'methods')
  plt.xlabel("Methods")
  plt.ylabel("Running times (seconds)")
  plt.xticks(rotation = 45)
  plt.legend(bbox_to_anchor = (1.1, 0.55))
  plt.savefig(f"{images_dir}/{fig_times}.pdf", bbox_inches="tight")
  
  # plotting heatmap with correlations paired according to p
  # creating subplots
  fig, axs = plt.subplots(nrows = 1, ncols = 3, figsize = (16, 10))
  
  # importing all cor data
  all_cor_data = ((pd.read_csv(original_path + folder_path + "/{}_stats.csv".format(kind))).
  rename(columns = {"Unnamed: 0" : "idx"}))
  
  # looping through p
  for p_sel, ax in zip(p, axs):
    cor_mat = (all_cor_data.
    query("p_var == @p_sel").
    query("stats in @vars_corr").
    pivot(
      index = "methods",
      columns = 'stats',
      values = 'value'
    ).
    corr(method = "spearman"))
    
    # plotting heatmap
    sns.heatmap(cor_mat,
    xticklabels = cor_mat.columns,
    yticklabels = cor_mat.columns,
    annot=True,
    cmap = "Blues",
    ax = ax,
    square = True,
    cbar_kws={"shrink": 0.4}
    )
    # setting title in each subplot
    ax.title.set_text('p = {}'.format(p_sel))
    ax.tick_params(labelsize = 8.25)
    
  
  # saving figure in correlation folder
  plt.tight_layout()
  plt.savefig(f"{images_dir}/{fig_corr}.pdf")
  
  # verifying mean marginal coverage and interval length
  data = (pd.read_csv(original_path + folder_path + "/{}_stats.csv".format(kind)).
  assign(sd = lambda df: df['sd']*2).
  query("p_var in @p").
  query("stats in @other_vars"))
  
  # sorting according to the custom order
  data['methods'] = data['methods'].astype(method_custom_order)
  data = data.sort_values('methods')
  
  # faceting all in a seaborn plot
  g = sns.FacetGrid(data, col = "stats", row = "p_var", hue = "methods",
  despine = False, margin_titles = True, legend_out = True,
  sharey = False,
  height = 5)
  g.map(plt.errorbar, "methods", "value", "sd", marker = "o")
  g.figure.subplots_adjust(wspace=0, hspace=0)
  g.add_legend(bbox_to_anchor = (1.1, 0.55))
  g.set_ylabels("Metric values")
  g.set_xlabels("Methods")
  g.set_titles(col_template="{col_name}", row_template = "{row_name}")
  g.set_xticklabels(rotation = 45)
  plt.tight_layout()
  plt.savefig(f"{images_dir}/{figname_others}.pdf", bbox_inches="tight")
  
  # finally, making line plots of all metrics against the number of relevant variables for each experiment
  data_final = data_main.sort_values('p_var')
  
  # using same data than before
  g = sns.FacetGrid(data_final.
  query("stats in @vars_to_plot"), col = "stats", col_wrap = 2, hue = "methods",
  hue_order =["locart", "Dlocart", "RF-locart", "RF-Dlocart", "Wlocart", "LCP-RF", "icp", "wicp", "mondrian"],
  despine = False, margin_titles = True, legend_out = True,
  sharey = False,
  height = 5)
  g.map(plt.errorbar, "p_var", "value", "sd", marker = "o")
  g.figure.subplots_adjust(wspace=0, hspace=0)
  g.add_legend(bbox_to_anchor = (1.1, 0.55))
  g.set_ylabels("Metric values")
  g.set_xlabels("p (relevant variables)")
  g.set_titles(col_template="{col_name}")
  g.set_xticklabels(rotation = 45)
  plt.tight_layout()
  plt.savefig(f"{images_dir}/{figname_p}.pdf", bbox_inches="tight")
  
  # returning data final to plot more general graphs
  return(data_final.assign(kind = kind_to_plot))
  

# plotting all at the same time
if __name__ == '__main__':
  print("plotting all results for wsc, smis and real diff")
  # selecting all p's
  p = np.array([1,3, 5])
  kinds_list = ["homoscedastic", "heteroscedastic", "asymmetric", "asymmetric_V2", 
  "t_residuals", "non_cor_heteroscedastic"]
  kinds_names = ["Homoscedastisc", "Heteroscedastic", "Asymmetric", "Asymmetric 2", 
  "T residuals", "Non-correlated heteroscedastic"]
  data_final_list = []
  time_data_list = []
  # path to times data set
  exp_path = "/results/pickle_files/locart_all_metrics_experiments/"
  
  for (kind, kind_name) in zip(kinds_list, kinds_names):
    if kind == "asymmetric_V2":
      other_asym = True
      kind = "asymmetric"
      folder_path = exp_path + kind + "_data"
      data_final_list.append(plot_results_by_methods(kind, p = p, other_asym = other_asym).assign(
        kind = kind_name))
      time_data_list.append(pd.read_csv(original_path + folder_path + "_eta_1.5" + "/{}_prop_times.csv".format(
        kind)).assign(kind = kind_name))
    else:
      folder_path = exp_path + kind + "_data"
      data_final_list.append(plot_results_by_methods(kind, p = p).assign(kind = kind_name))
      time_data_list.append(pd.read_csv(original_path + folder_path + "/{}_prop_times.csv".format(
        kind)).assign(kind = kind_name))
  
  props_time_all = pd.concat(time_data_list)
  vars_corr = np.array(["smis", "mean_valid_pred_set", "wsc", "pcor", "HSIC", "mean_diff", "max_diff"])
    
  images_dir = "results/metric_figures"
  figname_p = "performance_vs_p/general_regression_experiments"
  results_p = "performance_vs_p/general_results"
  corr_p = "correlations/general_corr_mat"
  fig_times_prop  = "times/all_times_proportion"
  
  method_custom_order = CategoricalDtype(
  ["locart", "Dlocart", "RF-locart", "RF-Dlocart", "Wlocart", "LCP-RF", "icp", "wicp", "mondrian"], 
  ordered=True)
  
  props_time_all['methods'] = props_time_all['methods'].astype(method_custom_order)
  data_final = (pd.concat(data_final_list).
  query("stats == 'mean_diff'"))
  
  # correlation data
  all_cor_data = pd.concat(data_final_list)
  
  g = sns.FacetGrid(data_final, col = "kind", col_wrap = 3,
  despine = False, margin_titles = True, legend_out = True,
  sharey = False,
  height = 5)
  g.map(sns.pointplot, "p_var", "value", "methods", 
  hue_order =  ["locart", "Dlocart", "RF-locart", "RF-Dlocart", "Wlocart", "LCP-RF", "icp", "wicp", "mondrian"],
  marker = "o",
  palette = "tab10",
  scale = 0.75)
  g.figure.subplots_adjust(wspace=0, hspace=0)
  g.set_ylabels("Mean difference metric")
  g.set_xlabels("p")
  g.set_titles(col_template="{col_name}")
  g.add_legend(bbox_to_anchor = (1.1, 0.55), title = "Methods")
  plt.tight_layout()
  plt.savefig(f"{images_dir}/{figname_p}.pdf", bbox_inches="tight")
  
  
  # barplot graph with frequency of methods with better mean difference
  data_count_mean_diff = (data_final.
  query("stats == 'mean_diff'").
  groupby(['p_var', 'kind']).
  apply(lambda df: df.nsmallest(n = 2, columns = 'value')).
  value_counts("methods"))
  
  # now with better smis
  data_count_smis = (pd.concat(data_final_list).
  query("stats == 'smis'").
  groupby(['p_var', 'kind']).
  apply(lambda df: df.nsmallest(n = 2, columns = 'value')).
  value_counts("methods"))
  
  # plotting count of data into two barplots
  fig, (ax1, ax2) = plt.subplots(nrows = 1, ncols = 2, figsize = (10, 6))
  ax1.bar(x = data_count_mean_diff.keys(), height = data_count_mean_diff.values,
  color = "tab:blue", alpha = 0.5)
  ax1.set_title("Mean difference")
  ax1.set_xlabel("Methods")
  ax1.set_ylabel("Frequency")
  ax1.tick_params(axis = "x", labelrotation=45)

  ax2.bar(x = data_count_smis.keys(), height = data_count_smis.values,
  color = "tab:blue", alpha = 0.5)
  ax2.set_title("Smis")
  ax2.set_xlabel("Methods")
  ax2.set_ylabel("Frequency")
  ax2.tick_params(axis = "x", labelrotation=45)
  
  plt.tight_layout()
  plt.savefig(f"{images_dir}/{results_p}.pdf")
  
  # plotting overall correlation heatmap
  plt.figure(figsize = (14, 10))

  # looping through p
  general_cor_list = []
  for p_sel in p:
    cor_list = []
    for kind_current in kinds_names:
      # obtaining correlation matrices for each kind
      cor_list.append(all_cor_data.
      query("p_var == @p_sel").
      query("stats in @vars_corr and kind == @kind_current").
      pivot(
        index = "methods",
        columns = 'stats',
        values = 'value'
      ).
      corr(method = "spearman"))
    
    # obtaining mean from correlation list
    columns_name = cor_list[0].columns
    cor_mat = np.mean(np.array(cor_list), axis = 0)
    general_cor_list.append(cor_mat)
    
  all_cor_mat = np.mean(np.array(general_cor_list), axis = 0)
  # plotting heatmap
  sns.heatmap(all_cor_mat,
  xticklabels = columns_name,
  yticklabels = columns_name,
  annot=True,
  cmap = "Blues",
  square = True,
  annot_kws={"size":12}
  )
  plt.savefig(f"{images_dir}/{corr_p}.pdf")
  
  
  plt.figure(figsize = (14, 12))
  sns.pointplot(data = props_time_all, x = "kind", y = "value", hue = "methods", 
  dodge = True, join=False, errorbar=('ci', 90), orient = "v", marker = "o", scale = 0.65)
  plt.xlabel("Data")
  plt.ylabel("Running time proportions")
  plt.yscale('log')
  plt.yticks([0.01, 0.1, 0.5, 1])
  plt.xticks(rotation = 45)
  plt.legend(bbox_to_anchor = (1.115, 0.55), title = "Methods")
  plt.savefig(f"{images_dir}/{fig_times_prop}.pdf", bbox_inches="tight")
  
  plt.close('all')
  
    
    
    
    