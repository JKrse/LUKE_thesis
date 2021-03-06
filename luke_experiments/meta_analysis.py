from torch.utils.tensorboard import SummaryWriter
import torch
import json
import os
import numpy as np

from argparse import Namespace
import click

from function_meta_analysis.functions import *

import matplotlib.pyplot as plt

# ==============================================================================
# Meta analysis for experiments 
# ==============================================================================


class config():
    tags = ["learning_rate", "seed", "train_batch_size", "train_frac_size", "hidden_dropout_prob", "weight_decay"]
    eval_sets = ["dev", "test"]


data_dir = "../data/outputs/seed_lr_wd_batch_train_size_dropout_with_eval_no_train"
output_dir = "."
tensorboard_plot = True
scatter_plot = True
calibration_plot = True
do_evaluate_prior_train = True

dpi = 300    

# with open("function_meta_analysis/name_change.json") as f: 
#     names_dict = json.load(f) 

# ==============================================================================

@click.command()
@click.option("--data-dir", default="data/outputs/seed_lr_wd_batch_train_size_dropout_with_eval_no_train", type=click.Path(exists=True))
@click.option("--output-dir", default="luke_experiments/plots_meta_analysis")
@click.option("--name-changing-file", default="luke_experiments/function_meta_analysis/name_change.json")
@click.option("--tensorboard-plot/--no-tensorboard-plot", default=True)
@click.option("--f1-training-plot/--no-f1-training-plot", default=True)
@click.option("--scatter-plot/--no-scatter-plot", default=True)
@click.option("--calibration-plot/--no-calibration-plot", default=True)
@click.option("--do-evaluate-prior-train/--no-evaluate-prior-train", default=True)
def run(**task_args):
    args = Namespace(**task_args)

    data_dir = args.data_dir    
    output_dir = args.output_dir
    names_dict_dir = args.name_changing_file
    tensorboard_plot =  args.tensorboard_plot
    f1_training_plot =  args.f1_training_plot
    scatter_plot = args.scatter_plot
    calibration_plot = args.calibration_plot
    do_evaluate_prior_train = args.do_evaluate_prior_train

    # Dictionary with name changes
    with open(names_dict_dir) as f: 
        names_dict = json.load(f)     
    
    tensorboard_event_folder = os.path.join(output_dir, "runs_tensorboards") 

    # Tag used for the tensorboard: 
    experiment_tags = config.tags

    eval_results = {}
    pred_logts = {}
    f1_scores = {}

    eval_results_with_tag = {}

    for experiment_tag in experiment_tags:
        eval_results[experiment_tag] = {}
        pred_logts[experiment_tag] = {}
        f1_scores[experiment_tag] = {}

        f1_eval = torch.tensor([])
        precision_eval = torch.tensor([])
        recall_eval = torch.tensor([])
        
        
        for root, dirs, files in os.walk(data_dir):

            result_json = os.path.join(root, "results.json")
            base_root = os.path.basename(root)
            
            if os.path.exists(result_json) and experiment_tag in base_root:
                
                # Load data:     
                with open(f"{result_json}") as json_file:
                    data = json.load(json_file)
                
                log_parameters = data["experimental_configurations"]["log_parameters"]
                par = log_parameters[f"{experiment_tag}"]
                gradient_accumulation_steps = log_parameters["gradient_accumulation_steps"]

                # Get parameters to model: 
                if len(data["training_loss"]) % gradient_accumulation_steps != 0: 
                    # print(f"Odd number of global_steps and training_loss: {base_root}")
                    data["training_loss"].append(data["training_loss"][-1])
                    training_loss = np.mean(np.array(data["training_loss"]).reshape(-1, gradient_accumulation_steps), axis=1)
                else: 
                    training_loss = np.mean(np.array(data["training_loss"]).reshape(-1, gradient_accumulation_steps), axis=1)

                ######################################################
                        #### Meta Analysis ####
                ######################################################

                ###########################
                # During training: 
                training_loss   = torch.tensor(training_loss)
                dev_f1          = torch.tensor([data[z] for z in data if "dev_f1_epoch" in z])
                dev_precision   = torch.tensor([data[z] for z in data if "dev_precision_epoch" in z])
                dev_recall      = torch.tensor([data[z] for z in data if "dev_recall_epoch" in z])


                ###########################
                # Development and Test evalution:
                ###########################
                # F1, Precision and Recall: 
                dev_f1_eval         = torch.tensor([data[z] for z in data if "dev_f1" in z and "_epoch" not in z])
                test_f1_eval        = torch.tensor([data[z] for z in data if "test_f1" in z])
                
                dev_precision_eval  = torch.tensor([data[z] for z in data if "dev_precision" in z and "_epoch" not in z])
                test_precision_eval = torch.tensor([data[z] for z in data if "test_precision" in z])
                
                dev_recall_eval     = torch.tensor([data[z] for z in data if "dev_recall" in z and "_epoch" not in z])
                test_recall_eval    = torch.tensor([data[z] for z in data if "test_recall" in z])


                # Data for F1 during training: 
                f1_scores[experiment_tag][base_root] = {}
                f1_scores[experiment_tag][base_root] = [data[z] for z in data if "dev_f1_epoch" in z]

                # Data for Scatter Plot: 
                eval_results[experiment_tag][base_root] = {}
                eval_results[experiment_tag][base_root]["f1"] = [dev_f1_eval, test_f1_eval]
                eval_results[experiment_tag][base_root]["precision"] = [dev_precision_eval, test_precision_eval]
                eval_results[experiment_tag][base_root]["recall"] = [dev_recall_eval, test_recall_eval]

                # For Calibration plots:   
                pred_logts[experiment_tag][base_root] = {}
                pred_logts[experiment_tag][base_root]["dev"] = data["evaluation_predict_label"]["dev"]
                pred_logts[experiment_tag][base_root]["test"] = data["evaluation_predict_label"]["test"]


                ######################################################
                    # TensorBoards: experimental based
                ######################################################
                
                # If event file already exists or not plotting tensorboards: 
                if not tensorboard_plot or os.path.exists(f"{tensorboard_event_folder}/{base_root}"):
                    continue
                else:
                    # Experimental based: 
                    tb = SummaryWriter(log_dir = f"{tensorboard_event_folder}/{base_root}")

                    for step, loss in enumerate(training_loss):
                        tb.add_scalar(f"{experiment_tag}/00.loss/Train", scalar_value=training_loss[step], global_step=step)
                    
                    for epoch, recall in enumerate(dev_f1):
                        tb.add_scalar(f"{experiment_tag}/01.f1/development", scalar_value=dev_f1[epoch], global_step=epoch)
                    
                    for epoch, precision in enumerate(dev_precision):
                        tb.add_scalar(f"{experiment_tag}/02.precision/development", scalar_value=dev_precision[epoch], global_step=epoch)
                        
                    for epoch, recall in enumerate(dev_recall):
                        tb.add_scalar(f"{experiment_tag}/03.recall/development", scalar_value=dev_recall[epoch], global_step=epoch)

                    tb.close()
            
        ######################################################
        # Evaluation: Experimental based
        ######################################################
        
        # F1 - scores during training
        if f1_scores[experiment_tag] and f1_training_plot:

            f1_scores[experiment_tag] = name_changes(f1_scores[experiment_tag], names_dict)

            labels = sorted(f1_scores[experiment_tag])
            if "a." in labels[0]:
                labels = [label[2:] for label in labels]
            
            title = labels[0].split("=")[0][:-1] 

            f1_plt = plot_f1(f1_scores[experiment_tag], labels, title=f"F1-score development set\n{title}", eval_prior_train=do_evaluate_prior_train)

            if not os.path.exists(f"{output_dir}/plots_f1_train"):
                os.makedirs(f"{output_dir}/plots_f1_train")
                
            f1_plt.savefig(f"{output_dir}/plots_f1_train/f1_train_{experiment_tag}", dpi=dpi)            

        # Scatter plot for dev and test:
        if eval_results[experiment_tag] and scatter_plot: 
            f1_eval, recall_eval, precision_eval = [], [], []   # experiment_tag = "learning_rate"

            eval_results[experiment_tag] = name_changes(eval_results[experiment_tag], names_dict)

            for experiment in sorted(eval_results[experiment_tag]):
                f1_eval.append(eval_results[experiment_tag][experiment]["f1"])
                precision_eval.append(eval_results[experiment_tag][experiment]["precision"])
                recall_eval.append(eval_results[experiment_tag][experiment]["recall"])

            eval_results_with_tag[experiment_tag] = {"f1" : np.array(flatten(f1_eval)).reshape(-1,2),
                                                    "precision" : np.array(flatten(precision_eval)).reshape(-1,2),
                                                    "recall" : np.array(flatten(recall_eval)).reshape(-1,2)}
            
            labels = sorted(eval_results[experiment_tag])
            if "a." in labels[0]:
                labels = [label[2:] for label in labels]
            
            title = labels[0].split("=")[0][:-1] 

            scatter_plt = plot_scatter(eval_results_with_tag[experiment_tag], labels, title=title)

            if not os.path.exists(f"{output_dir}/plots_scatter"):
                os.makedirs(f"{output_dir}/plots_scatter")
                
            scatter_plt.savefig(f"{output_dir}/plots_scatter/dev_test_{experiment_tag}", dpi=dpi)
        

        # Calibration Plot for dev and test seperately: 
        if pred_logts[experiment_tag] and calibration_plot: 
            
            if not os.path.exists(f"{output_dir}/plots_calibration"):
                os.makedirs(f"{output_dir}/plots_calibration")

            for eval_set in config.eval_sets:
        
                true = []
                pred = []
            
                labels = []
                true_temp = np.array([])
                pred_temp = np.array([])

                pred_logts[experiment_tag] = name_changes(pred_logts[experiment_tag], names_dict)
                
                for experiment in sorted(pred_logts[experiment_tag]):
                    labels.append(experiment)

                    true_temp = np.concatenate(pred_logts[experiment_tag][experiment][eval_set]["true_labels"])
                    pred_temp = np.concatenate(pred_logts[experiment_tag][experiment][eval_set]["predict_logits"])
                    pred_temp = logit2prob(pred_temp)
                
                    true.append(true_temp)
                    pred.append(pred_temp)

                labels = sorted(eval_results[experiment_tag])
                if "a." in labels[0]:
                    labels = [label[2:] for label in labels]

                if eval_set == "test":
                    title = "Test set"
                if eval_set == "dev":
                    title = "Development set"

                if "robust_" in labels[0]:
                    labels = [label[7:] for label in labels]
                cal_plot = plot_calibration_curve_with_hist(true, pred, model_name=labels, title=title, n_bins=10)

                cal_plot.savefig(f"{output_dir}/plots_calibration/{experiment_tag}_{eval_set}", dpi=dpi)
                

# ==============================================================================

if __name__ == '__main__':
    run()