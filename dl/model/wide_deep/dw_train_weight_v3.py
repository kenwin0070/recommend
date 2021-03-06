#coding:utf-8
"""train the lr model"""

import argparse
import configparser
import logging
import reprlib
import sys
import os

import tensorflow as tf


#sys.path.append("../../../tftools")
sys.path.append("/data4/timmyqiu/qmkg/TensorFlowRec/tftools")

from FCGen import FCGen
from Trainer.Models.LinearModel import input_fn

def configure(parser):
  parser.add_argument(
    '--conf', type=str, help='param configuration file is requried'
  )
  parser.add_argument(
    '--train', type=str, help='param configuration file is requried'
  )
  parser.add_argument(
    '--dev', type=str, help='param configuration file is requried'
  )

def input_receiver(feature_spec):
  serialized_tf_example = tf.placeholder(dtype=tf.string,
                                         shape=[None],
                                         name='input')
  receiver_tensors = {'examples': serialized_tf_example}
  features = tf.parse_example(serialized_tf_example, feature_spec)
  rec = tf.estimator.export.ServingInputReceiver(features, receiver_tensors)
  print('rec:', rec)
  return rec  
  
  
def train(config , trainfile, testfile):
  """Entry for trainig

  Args:
    config: (configparser) All the hyperparameters for training
  """
  train_dir = trainfile
  train_files = [os.path.join(train_dir, f) for f in os.listdir(train_dir) if f != "_SUCCESS"]
  logging.info('train directory: {}'.format(train_dir))
  logging.info('train files: {}'.format(reprlib.repr(train_files)))

  dev_dir = testfile
  dev_files = [os.path.join(dev_dir, f) for f in os.listdir(dev_dir) if f != "_SUCCESS"]
  logging.info('dev directory: {}'.format(dev_dir))
  logging.info('dev files: {}'.format(reprlib.repr(dev_files)))
  #特征的配置文件 在input 这个section的spec这个key
  feature_config = configparser.ConfigParser()
  feature_config.read(config['input']['spec'])#特征配置文件 有boundaries等信息
  columns, spec = FCGen.GetFeatureSpec(feature_config)#按特征列对特征进行处理，不同类型处理会不一样，比如数值、embed等

  batch_size = int(config['train']['batch_size'])

  conf = tf.ConfigProto()  
  conf.gpu_options.allow_growth=True  

  os.environ["CUDA_VISIBLE_DEVICES"] = "3"
  run_config = tf.estimator.RunConfig().replace(
      session_config=conf)

  
  logging.info("Creating model...")
  # Define the model
  #hidden_units = [int(n) for n in config['dnn_model']['hidden_units'].split(',')]
  #dropout = config['dnn_model'].get('dropout', '')
  #if dropout == '':
  #  dropout = None
  #else:
  #  dropout = float(dropout)
  #print(columns['weight'][0])#如果有weight这个就不能注释
  model = tf.estimator.DNNLinearCombinedClassifier(
            config=run_config,
            model_dir=config['train'].get('model_dir', 'model_dir'),
            linear_feature_columns=columns['linear'],
            linear_optimizer=tf.train.FtrlOptimizer(
              learning_rate=float(config['linear_model']['learning_rate']),
              l1_regularization_strength=float(config['linear_model']['l1_reg']),
              l2_regularization_strength=float(config['linear_model']['l2_reg'])),
            #dnn_feature_columns=columns['dnn'],#没有dnn的话这个就注销
            #dnn_hidden_units=hidden_units,
            #weight_column=columns['weight'][0],#如果有weight这个就不能注释
            #dnn_optimizer=tf.train.AdamOptimizer(
            #  learning_rate=float(config['dnn_model']['learning_rate'])),
            #dnn_dropout=dropout,
            loss_reduction=tf.losses.Reduction.SUM_OVER_BATCH_SIZE)

  # Train and evaluate
  max_steps = config['train'].get('max_step', '')
  if max_steps == '':
    max_steps = None
  else:
    max_steps = int(max_steps)

  logging.info("training...")
  model.train(input_fn=lambda: input_fn(train_files, spec, shuffle=True, batch_size=batch_size),
              steps=max_steps)

  results = model.evaluate(input_fn=lambda: input_fn(dev_files, spec, shuffle=False, batch_size=batch_size))

  logging.info("results...")
  for key in sorted(results):
    print('%s: %s' % (key, results[key]))

  model.export_savedmodel(export_dir_base=config['train'].get('export_dir', 'export_dir'), 
      serving_input_receiver_fn=lambda: input_receiver(spec),
      strip_default_attrs=True) 

if __name__ == '__main__':
  logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
  parser = argparse.ArgumentParser()
  configure(parser) 
  FLAGS, _ = parser.parse_known_args()

  config = configparser.ConfigParser()  
  config.read(FLAGS.conf)

  seed = int(config['train'].get('seed', 19910825))
  tf.set_random_seed(seed)

  train(config ,FLAGS.train , FLAGS.dev)
