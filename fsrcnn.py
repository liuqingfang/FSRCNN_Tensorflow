import cv2
import tensorflow as tf 
import numpy as np 
import os

def prelu(_x):
    """
    Parametric ReLU
    """
    alphas = tf.get_variable('alpha', _x.get_shape()[-1],
                       initializer=tf.constant_initializer(0.1),
                        dtype=tf.float32, trainable=True)
    pos = tf.nn.relu(_x)
    neg = alphas * (_x - abs(_x)) * 0.5

    return pos + neg

def model(LR_input, HR_output, scale, batch, lr, (d, s, m)):
    """
    Implementation of FSRCNN: http://mmlab.ie.cuhk.edu.hk/projects/FSRCNN.html
    Parameters
    ----------
    scale: int
        super-resolution scale
    LR_input:
        input LR dataset
    HR_output:
        output HR dataset
    (d, s, m):
        fsrcnn model parameters
    Returns
    ----------
    Model
    """

    channels = 1
    bias_initializer = tf.constant_initializer(value=0.0)

    filters = [
        tf.Variable(tf.random_normal([5, 5, 1, d], stddev=0.1), name="f1"),           # (f1,n1,c1) = (5,64,1)
        tf.Variable(tf.random_normal([1, 1, d, s], stddev=0.1), name="f2"),           # (f2,n2,c2) = (3,12,56)
        tf.Variable(tf.random_normal([1, 1, s, d], stddev=0.1), name="f%d" % (3 + m)),# (f4,n4,c4) = (1,56,12)
        tf.Variable(tf.random_normal([9, 9, 1, d], stddev=0.1), name="f%d" % (4 + m)) # (f5,n5,c5) = (9,1,56) #should be 9,9,d,1? -- 9,1,d like paper
    ]
    bias = [
        tf.get_variable(shape=[d], initializer=bias_initializer, name="b1"),
        tf.get_variable(shape=[s], initializer=bias_initializer, name="b2"),
        tf.get_variable(shape=[d], initializer=bias_initializer, name="b%d" % (3 + m)),
        tf.get_variable(shape=[1], initializer=bias_initializer, name="b%d" % (4 + m))
    ]
    # add filters and biases for 'non-linear mapping' layers (depeding on m), and name them in order
    for i in range(0,m):
        filters.insert(i+2, tf.Variable(tf.random_normal([3, 3, s, s], stddev=0.1), name="f%d" % (3+i)))  # (f3,n3,c3) = (3,12,12)
        bias.insert(i+2, tf.get_variable(shape=[s], initializer=bias_initializer, name="b%d" % (3+i)))

    # -- Layers --
    # feature extraction
    x = tf.nn.conv2d(LR_input, filters[0], [1, 1, 1, 1], padding='SAME', name="conv1")
    x = x + bias[0]
    #x = prelu(x)
    x = tf.nn.relu(x)
    print("feature extraction layer output.shape: ")
    print(x.shape)

    # shrinking
    x = tf.nn.conv2d(x, filters[1], [1, 1, 1, 1], padding='SAME', name="conv2")
    x = x + bias[1]
    #x = prelu(x)
    x = tf.nn.relu(x)
    print("shrinking layer output.shape: ")
    print(x.shape)

    # non-linear mapping (amount of layers depends on m)
    for i in range(0,m):
        x = tf.nn.conv2d(x, filters[2+i], [1, 1, 1, 1], padding='SAME', name="conv%d" % (3+i))
        x = x + bias[2+i]
        #x = prelu(x)
        x = tf.nn.relu(x)
    print("n-l mapping layer output.shape: ")
    print(x.shape)

    # expanding
    x = tf.nn.conv2d(x, filters[3+(m-1)], [1, 1, 1, 1], padding='SAME', name="conv%d" % (3+m))
    x = x + bias[3+(m-1)]
    #x = prelu(x)
    x = tf.nn.relu(x)
    print("expanding layer output.shape: ")
    print(x.shape[0])
    print(x.shape[1])
    print(x.shape[2])
    print(x.shape[3])
    
    output_shape = [batch,int(x.shape[1]*scale), int(x.shape[2]*scale), 1]
    # deconvolution a.k.a. transposed convolution
    #tf.nn.conv2d_transpose(value, filter,output_shape,strides,padding='SAME',data_format='NHWC',name=None)
    x = tf.nn.conv2d_transpose(x, filters[4+(m-1)], output_shape, [1, scale, scale, 1], padding='SAME', name="deconv")
    print("deconv successful")
    out = x + bias[4+(m-1)]
    print("deconv out.shape=")
    print(out.shape)

    out = tf.reshape(out, out.shape, name = "NHWC_output")
    # out = tf.nn.tanh(out, name="NHWC_output")
    # bsize, a, b, c = l3.get_shape().as_list()
    # out_nchw = tf.reshape(out, (-1, 1, a * scale, b * scale), name="NCHW_output")

    psnr = tf.image.psnr(out, HR_output, max_val=1.0)

    loss = tf.losses.mean_squared_error(out, HR_output)
    train_op = tf.train.AdamOptimizer(learning_rate=lr).minimize(loss)

    return out, loss, train_op, psnr


