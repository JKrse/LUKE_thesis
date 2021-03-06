import pickle
import numpy as np
import os
import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
plt.rcParams.update({'font.size': 30, 'legend.fontsize': 20})
plt.rc('font', size=25)
plt.rc('axes', titlesize=25)
from tqdm import tqdm

# =============================================================== #


def attention_scores_and_mean_in_layer_bins(data_dir, mask_index=-2, number_of_bins=5, include_only_token_len=None, eval_sets = ["test", "dev"]):
    '''
    Given add data_dir it will convert the attention scores (layer x head x seq_len x seq_len) 
    into bins, both "raw" (only converting into bins) and the mean attention score for each bin
    '''
    def attention_in_bins(attention, bins_dict): 
        '''
        Splitting the attention scores into bins
        bin_ranges = {bin_x1 : range(p0, p1), bin_x2 : range(p1, p2), ...} 
        '''
        bin_attention = {}
        bins_names = list(bin_ranges)

        for l, layer in enumerate(attention):
            bin_attention[f"layer_{l}"] = {}

            for h, head in enumerate(layer):
                bin_attention[f"layer_{l}"][f"head_{h}"] = {}

                for i, bin_ in enumerate(bin_ranges.values()):            
                    start = bin_[0]
                    end = bin_[-1]+1
                    bin_attention[f"layer_{l}"][f"head_{h}"][bins_names[i]] = head[-2][start:end]
            
        return bin_attention

    def mean_attention_scores_in_bins(attention_in_bins_, bins_names):
        '''
        Get the mean attention_scores for each bin in each layer
        '''
        mean_attention_scores_layer = {}
        
        for bin_ in bins_names: 
            mean_attention_scores_layer[bin_] = {}
            for l, layer in enumerate(attention_in_bins_.values()):
                head_bin_values = []
                for head_bin_value in layer.values():
                    # Append all bin values: 
                    head_bin_values.extend(head_bin_value[bin_].tolist())    
                # Layer mean across all heads: 
                layer_mean = np.mean(head_bin_values)

                mean_attention_scores_layer[bin_][f"layer_{l}"] = layer_mean
            
        return mean_attention_scores_layer

    all_attention_scores_in_bins = {}
    all_attention_scores_in_bins_mean = {}
    
    tokens_in_sentence = []
    sentences = []
    for eval_set in eval_sets:
        attention_scores_in_bins = {}
        mean_attention_layer_in_bins = {}
        data = pickle.load(open( os.path.join(data_dir, f"output_attentions_{eval_set}.p"), "rb"))
        
        for example in data.keys():
            # Sanity check:     
            tokens = data[example]["tokens"]
            if tokens[mask_index] not in "[MASK]":
                print(f"[not included] Sample: {example} did not have [MASK].")
                continue
            
            attention        = data[example]["attention"]
            number_of_tokens = len(data[example]["tokens"][:-2]) 

            if number_of_bins > number_of_tokens: 
               print(f"[not included] Sample: {example} has {number_of_tokens} tokens but was asked for {number_of_bins} bins")
               continue
            if include_only_token_len is not None:
                if number_of_tokens is not include_only_token_len:
                    continue
            
            tokens_in_sentence.append(number_of_tokens)
            sentences.append(data[example]["sentence"])

            # Use functions: 
            # Bins: 
            bin_ranges = output_bin_ranges(number_of_bins, number_of_tokens)
            # Attention scores in bins: 
            attention_scores_in_bins[example]       = attention_in_bins(attention, bin_ranges)
            # Mean attention scores in bins: 
            mean_attention_layer_in_bins[example]   = mean_attention_scores_in_bins(attention_scores_in_bins[example], list(bin_ranges))

        all_attention_scores_in_bins[eval_set] = attention_scores_in_bins
        all_attention_scores_in_bins_mean[eval_set] = mean_attention_layer_in_bins
    
    return all_attention_scores_in_bins, all_attention_scores_in_bins_mean, tokens_in_sentence, list(bin_ranges), sentences


def output_bin_ranges(number_of_bins, number_of_tokens):
    '''
    Generate the bin intervals. Note, we it is the tokens: 
    <s> .... </s> AND [MASK]
    The latter is not included in the bins. The [PAD] token always have
    0 attention score for [MASK] -> [PAD], thus, not included. 
    
    For number_of_bins=3, number_of_tokens=5 
    output => {0: range(0, 1), 1: range(1, 2), 2: range(2, 5), 'mask': range(5, 6)}

    e.g.    6: tensor([0.3243]),
            7: tensor([0.0409]),
            8: tensor([0.0148, 0.0158, 0.0642, 0.0152, 0.1872]
            'mask': tensor([0.0780])
    
    All of equal size except last and "mask". Last will include all the rest of the tokens. 
    '''
    assert number_of_bins <= number_of_tokens, f"Input {number_of_bins} bins for {number_of_tokens} tokens"

    samples_in_each_bin = int(np.round(number_of_tokens/number_of_bins))

    while samples_in_each_bin*number_of_bins > number_of_tokens:
        samples_in_each_bin -= 1# samples_in_each_bin*number_of_bins>
        #print("not good")

    bin_ranges = {}
    for i in range(number_of_bins): 
        if i == 0:
            bin_ranges[i] = range(0,samples_in_each_bin)
        else: 
            prev_bin = bin_ranges[i-1]
            bin_start = prev_bin[-1]+1
            bin_end = prev_bin[-1]+samples_in_each_bin+1

            bin_ranges[i] = range(bin_start, bin_end)
    
    # if bin_ranges[i][-1] > number_of_tokens:
    #     bin_ranges[i] = range(bin_ranges[i][0], number_of_tokens)
    # bin_ranges["mask"] = range(bin_ranges[i][-1]+1, bin_ranges[i][-1]+2)
    
    if bin_ranges[i][-1] < number_of_tokens:
        bin_ranges[i] = range(bin_ranges[i][0], number_of_tokens)

    bin_ranges["mask"] = range(number_of_tokens, number_of_tokens+1)

    return bin_ranges


def collect_all_attention_scores_from_bins(mean_attention_scores_bins, bin_names, eval_sets=["dev", "test"]):
    '''
    Short all attention scores into bins (both dev/test) 
    -> {bin_0 : {attention_scores_layers}, bin_1 :{}, ... }: 
    '''
    collect_attention_mean_all_examples = {}
    
    for bin_ in bin_names:
        mean_values = []
        for eval_set in eval_sets:
            for example in mean_attention_scores_bins[eval_set].keys():            
                mean_values.append(mean_attention_scores_bins[eval_set][example][bin_])

        collect_attention_mean_all_examples[bin_] = mean_values
    
    return collect_attention_mean_all_examples


def get_mean_attention_in_bins_from_layers(attention_examples_in_bins):
    '''
    Get the avg. attention for all examples in the bins 
    Output: dictionary -> {bin_0 : {mean_scores_for_all_examples_across_layers}, bin_1 :{}, ... }:
    '''
    bin_names = list(attention_examples_in_bins.keys())

    mean_attention_bins_layers = {}
    var_attention_bins_layers = {}
    SE_attention_bins_layers = {}
    for bin_ in bin_names:

        # Compute the mean: mu = sim(xi)/N
        for i, example_in_bin in enumerate(attention_examples_in_bins[bin_]):
            if i == 0:
                add_attention_layer_in_bin = np.array(list(example_in_bin.values()))
            else: 
                add_attention_layer_in_bin = add_attention_layer_in_bin + np.array(list(example_in_bin.values()))
        
        number_of_samples = len(attention_examples_in_bins[bin_])
        
        mean_attention_bins_layers[bin_] = add_attention_layer_in_bin / number_of_samples

        # Variance^2 = sum (xi - mu)^2 / (N-1) 
        for i, example_in_bin in enumerate(attention_examples_in_bins[bin_]):
            if i == 0: # p = (xi - mu)^2
                add_attention_layer_in_bin = (np.array(list(example_in_bin.values())) - mean_attention_bins_layers[bin_])**2
            else: # p = p + (xi - mu)^2
                add_attention_layer_in_bin = add_attention_layer_in_bin + (np.array(list(example_in_bin.values())) - mean_attention_bins_layers[bin_])**2

        # var^2 = p / (n-1)
        var_attention_bins_layers[bin_] = add_attention_layer_in_bin / (number_of_samples-1)

        # SE = sqrt(var)/sqrt(N)
        SE_attention_bins_layers[bin_] = np.sqrt(var_attention_bins_layers[bin_])/np.sqrt(number_of_samples)
    
    return mean_attention_bins_layers, var_attention_bins_layers, SE_attention_bins_layers


def plot_hist_token_len(tokens_len, bins=50, title=None):
    '''
    Generate histogram for token len distribution
    Input: list of integers [36, 2, 90, ...]
    Output: figure with histogram 
    '''
    # Statistic analysis: 
    number_of_samples = len(tokens_len)
    mean_ = np.mean(tokens_len)
    std_ = np.std(tokens_len)
    min_ = np.min(tokens_len)
    max_ = np.max(tokens_len)
    
    if title is None:
        title=f"Tokens in sentences distribution\nNumber of samples: {number_of_samples}, bins: {bins}"
    #label = [f"Number of samples: {number_of_samples}"]

    # ==== Figure ==== #
    figure, ax = plt.subplots(figsize=(12,9))
    ax.hist(tokens_len,bins=bins)
    # ax.hist(tokens_len, label=label[0],bins=bins)

    plt.axvline(x=max_, label=f'Max = {max_:.2f}', c="green")
    plt.axvline(x=min_, label=f'Min = {min_:.2f}', c="green")
    plt.axvline(x=mean_, label=f'$\mu$= {mean_:.2f}', c="black")
    plt.axvline(x=mean_+std_, label=f'$\sigma$: {std_:.2f}', c="red")
    plt.axvline(x=mean_-std_, c="red")

    ax.set_title(title, size="x-large") 
    ax.set_xlabel("Number of token in sentence", fontsize="large")
    ax.set_ylabel("Count", fontsize="large")
    ax.legend()


    plt.tick_params(axis='x', labelsize="large")
    plt.tick_params(axis='y', labelsize="large")
    plt.grid()
    plt.tight_layout()

    return figure 


def plot_bins_attention_scores_mean(mean_attention_bins_layers, SE_attention_bins_layers, title="Average attention score for sentence in bins", mask_to_mask=False): 
    '''
    Plot the average attention scores from bins
    Input: mean_attention_bins_layers
    Output: figure with avg. attention scores in bins
    '''
    keys = list(mean_attention_bins_layers)
    
    top_x_to_inlude = 11
    if len(keys) > top_x_to_inlude:
        global_means = get_global_mean_attention_bins(mean_attention_bins_layers, save=False)
        index = sorted(np.array(list(global_means.values())).argsort()[-top_x_to_inlude:][::-1])
        keys = [keys[ind] for ind in index]

    labels = [f"{lab} (acc. attn. {np.mean(mean_attention_bins_layers[lab]):.2f})" for lab in keys]

    number_of_layers = len(mean_attention_bins_layers[bin_names[0]])
    colors = ["b", "g", "c", "m", "brown", "purple", "navy", "pink", "gray", "olive", "black"]
    # if len(colors) < len(bin_names):
    #     colors = list(mcolors.CSS4_COLORS)[20:]
    
    # ==== Figure ==== #
    figure, ax = plt.subplots(figsize=(18,10))
    
    for i, bin_ in enumerate(keys):
        if mask_to_mask:
            if bin_ == "mask":
                # plt.plot(range(number_of_layers), mean_attention_bins_layers[bin_], "o--", color="black", label=labels[-1])
                ax.errorbar(range(number_of_layers), mean_attention_bins_layers[bin_], yerr=SE_attention_bins_layers[bin_], label=labels[-1], color="black")
        else:
            if bin_ == "mask":
                continue
                ax.plot(range(number_of_layers), mean_attention_bins_layers[bin_], "o--", color="black")
            else:
                # ax.plot(range(number_of_layers), mean_attention_bins_layers[bin_], "o-", color=colors[i])
                ax.errorbar(range(number_of_layers), mean_attention_bins_layers[bin_], yerr=SE_attention_bins_layers[bin_], color=colors[i])
    
    if not mask_to_mask:
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width*0.6, box.height])
        legend1 = ax.legend(labels[:], loc='lower left', bbox_to_anchor=(1, 0), 
                            edgecolor="white", title="Bin", fontsize="medium")
        ax.add_artist(legend1)

    ax.set_title(title, size="x-large") 
    ax.set_xlabel("Layer", fontsize="large")
    ax.set_ylabel("Avg. attention score", fontsize="large")
    ax.set_xticks(range(0, number_of_layers, 2))
    ax.set_xticklabels(range(0,number_of_layers, 2))
    plt.legend()
    plt.tick_params(axis='x', labelsize="large")
    plt.tick_params(axis='y', labelsize="large")
    plt.grid()
    plt.tight_layout(rect=[0,0,0.74,1])

    return figure


def get_global_mean_attention_bins(mean_attention_bins_layers, output_dir=".", save=True):
    '''
    Sum the global attention for each bins. Gives an intuative feeling of the number of bins.
    Save and it dumps the file as txt.
    '''
    global_mean_in_bin = {}
    for bin_ in mean_attention_bins_layers.keys():
        global_mean_in_bin[bin_] = np.mean(mean_attention_bins_layers[bin_])
        
    num_bins = len(mean_attention_bins_layers)-1
    if save: 
        with open(f'{output_dir}/bins_{num_bins}.txt', 'w') as outfile:
            json.dump(global_mean_in_bin, outfile)
    
    return global_mean_in_bin


def attention_to_entity(data_dir, eval_set = "test", mask_index = -2, include_only_token_len=None):
    
    def entity_layer_mean(attention, entity_idx, mask_index=-2):
        layer_mean = []
        for layer in attention:
            head_mean = []
            for head in layer:
                temp_mean_head_attn = []
                if entity_idx[0] is not entity_idx[1]:
                    for i in range(entity_idx[0], entity_idx[1]+1):
                        temp_mean_head_attn.append(head[mask_index][i])
                else: 
                    temp_mean_head_attn.append(head[mask_index][entity_idx[0]])
                head_mean.append(np.mean(temp_mean_head_attn))
            layer_mean.append(np.mean(head_mean))
        return layer_mean

    def entity_index(tokens):
        index = []
        for i, token in enumerate(tokens): 
            if token == "[ENTITY]": 
                index.append(i)
        
        index[0] = index[0]+1 
        index[1] = index[1]-1 
        
        # if index[0] == index[1]:
        #     index = index[0]

        return index

    #for eval_set in eval_sets:
    mean_attention_layer_mask_to_entity_2 = {}
    mean_attention_layer_mask_to_entity_rest = {}
    data = pickle.load(open( os.path.join(data_dir, f"output_attentions_{eval_set}.p"), "rb"))

    # mask to entity
    for sent in data: 
        tokens = data[sent]["tokens"]
        number_of_tokens = len(tokens)
        if include_only_token_len is not None:
            if number_of_tokens is not include_only_token_len:
                continue
        
        attention = data[sent]["attention"]
        entity_idx = entity_index(tokens)
        mask_to_entity_attn = entity_layer_mean(attention, entity_idx, mask_index)
        if entity_idx[0] is 2:
            mean_attention_layer_mask_to_entity_2[sent] = mask_to_entity_attn
        else:
            mean_attention_layer_mask_to_entity_rest[sent] = mask_to_entity_attn
        
    return mean_attention_layer_mask_to_entity_2, mean_attention_layer_mask_to_entity_rest


def plot_mask_to_entity(attn2entity_2_dict, title="[MASK]$\longrightarrow$[ENTITY]"):

    attn_val_mean = []
    for i, attn_val in enumerate(attn2entity_2_dict.values()): 
        if i is 0: 
            attn_val_mean = np.array(attn_val)
        else: 
            attn_val_mean = attn_val_mean + np.array(attn_val)    
    attn_val_mean = attn_val_mean/(i+1)

    number_of_layers = len(attn_val_mean)

    figure, ax = plt.subplots(figsize=(12,9))

    for example in attn2entity_2_dict.values():
        ax.plot(range(len(attn_val_mean)), example)
    ax.plot(range(len(attn_val_mean)), attn_val_mean, 'go--', linewidth=2, markersize=12, label="Mean attention curve")

    ax.set_title(title, size="x-large") 
    ax.set_xlabel("Layer", fontsize="large")
    ax.set_ylabel("Attention score", fontsize="large")
    ax.set_xticks(range(0, number_of_layers, 2))
    ax.set_xticklabels(range(0,number_of_layers, 2))
    plt.legend()
    plt.tick_params(axis='x', labelsize="large")
    plt.tick_params(axis='y', labelsize="large")
    plt.grid()
    plt.tight_layout()

    return figure
    

# =============================================================== #
# data_dir = "/Users/johanneskruse/Desktop/output_attentions_full_dev_test"
# data_dir = "/Users/johanneskruse/Desktop/dev_test"
# output_dir = "plot_attention_visualization"
# number_of_bins = 4

data_dir = "data/outputs/output_attentions_full_dev_test"
output_dir = "visual_attention/tests/plot_attention_visualization"

if not os.path.exists(output_dir):
    os.mkdir(output_dir)
            

for number_of_bins in tqdm([2, 4, 8, 16, 35, 50, 64, 72, 84, 97, 98, 114]): # 32: 142, 33: 145, 34: 135, 35: 150
    # Get attention scores in bins, mean of each bin, the len of all tokens, and the bin names: 
    if number_of_bins in [35, 50, 64, 72, 84, 97, 98, 114]:
        attention_scores_bins, mean_attention_scores_bins, tokens_len, bin_names, sentences = attention_scores_and_mean_in_layer_bins(data_dir, number_of_bins=number_of_bins, include_only_token_len=number_of_bins)
    else:
        attention_scores_bins, mean_attention_scores_bins, tokens_len, bin_names, sentences = attention_scores_and_mean_in_layer_bins(data_dir, number_of_bins=number_of_bins, include_only_token_len=None)

    # Short all attention scores into bins (both dev/test) -> {bin_0 : {attention_scores_layers}, bin_1 :{}, ... }: 
    attention_examples_in_bins = collect_all_attention_scores_from_bins(mean_attention_scores_bins, bin_names)

    # Get the avg. attention for all examples in the bins -> {bin_0 : {mean_scores_for_all_examples_across_layers}, bin_1 :{}, ... }:
    mean_attention_bins_layers, var_attention_bins_layers, SE_attention_bins_layers = get_mean_attention_in_bins_from_layers(attention_examples_in_bins)
    
    # Dump files with the global attention for each bin.
    _ = get_global_mean_attention_bins(mean_attention_bins_layers, output_dir=output_dir, save=True)
    
    # ========================== #
    ### Plot
    token_hist_plt = plot_hist_token_len(tokens_len=tokens_len, bins=100)
    avg_attention_bins_plt = plot_bins_attention_scores_mean(mean_attention_bins_layers, SE_attention_bins_layers, title=f"Average attention score for sentence in bins\nNo. samples={len(tokens_len)}, with errors bars")
    avg_attention_bins_plt_mask = plot_bins_attention_scores_mean(mean_attention_bins_layers, SE_attention_bins_layers, title=f"Average attention score [mask]$\longrightarrow$[mask] attention\nNo. samples={len(tokens_len)}", mask_to_mask=True)


    save = True
    if save: 
        print(f"saving plots... {output_dir}")
        dpi = 300
        token_hist_plt.savefig(f"{output_dir}/plot_token_len_hist_{number_of_bins}", dpi=dpi)
        avg_attention_bins_plt.savefig(f"{output_dir}/plot_avg_attention_bins_plt_bins_{number_of_bins}", dpi=dpi)
        avg_attention_bins_plt_mask.savefig(f"{output_dir}/plot_avg_attention_bins_mask_to_mask", dpi=dpi)

        # Save sentence examples:
        with open(f"{output_dir}/sentences_{number_of_bins}", 'w') as filehandle:
            for listitem in sentences:
                filehandle.write('%s\n' % listitem)

    save_mask_to_entity = True
    if save_mask_to_entity:
        for eval_set in ["dev", "test"]:
            if number_of_bins in [35, 50, 64, 72]:
                attn_MASK_to_ENTITY_position_2, attn_MASK_to_ENTITY_position_rest = attention_to_entity(data_dir, eval_set=eval_set, include_only_token_len=number_of_bins)
                plot_mask_to_entity_2 = plot_mask_to_entity(attn_MASK_to_ENTITY_position_2, title=f"Position: only 2 ({eval_set}, bins: {number_of_bins})\n[MASK]$\longrightarrow$[ENTITY]")
                plot_mask_to_entity_not_2 = plot_mask_to_entity(attn_MASK_to_ENTITY_position_rest, title=f"Position: exclude 2 ({eval_set}, bins: {number_of_bins})\n[MASK]$\longrightarrow$[ENTITY]")
            else:
                attn_MASK_to_ENTITY_position_2, attn_MASK_to_ENTITY_position_rest = attention_to_entity(data_dir, eval_set=eval_set)
                plot_mask_to_entity_2 = plot_mask_to_entity(attn_MASK_to_ENTITY_position_2, title=f"Position: only 2 ({eval_set}, bins: {number_of_bins})\n[MASK]$\longrightarrow$[ENTITY]")
                plot_mask_to_entity_not_2 = plot_mask_to_entity(attn_MASK_to_ENTITY_position_rest, title=f"Position: exclude 2 ({eval_set}, bins: {number_of_bins})\n[MASK]$\longrightarrow$[ENTITY]")
                
        
        plot_mask_to_entity_2.savefig(f"{output_dir}/plot_mask_to_entity_2_bins_{number_of_bins}", dpi=dpi)
        plot_mask_to_entity_not_2.savefig(f"{output_dir}/plot_mask_to_entity_not_2_bins_{number_of_bins}", dpi=dpi)




# =============================================================== #
sanity = False
# Sanity check: 
if sanity:
    p = []
    for head in attention_scores_bins["dev"]["sent_0"]["layer_0"].values():
        p.append(head[0].tolist())
    np.mean(p)
    mean_attention_scores_bins["dev"]["sent_0"][0]["layer_0"]

    # Done correctly
    data = pickle.load(open( os.path.join(data_dir, f"output_attentions_test.p"), "rb"))
    data["sent_28"]["attention"][0][0][-2]
    attention_scores_bins["dev"]["sent_28"]["layer_0"]["head_0"]
